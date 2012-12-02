#include "rar.hpp"

#include "rarvmtbl.cpp"

RarVM::RarVM()
{
  Mem=NULL;
}


RarVM::~RarVM()
{
  delete[] Mem;
}


void RarVM::Init()
{
  if (Mem==NULL)
    Mem=new byte[VM_MEMSIZE+4];
}

/*********************************************************************
 IS_VM_MEM macro checks if address belongs to VM memory pool (Mem).
 Only Mem data are always low endian regardless of machine architecture,
 so we need to convert them to native format when reading or writing.
 VM registers have endianness of host machine.
**********************************************************************/
#define IS_VM_MEM(a) (((byte*)a)>=Mem && ((byte*)a)<Mem+VM_MEMSIZE)

inline uint RarVM::GetValue(bool ByteMode,uint *Addr)
{
  if (ByteMode)
  {
#ifdef BIG_ENDIAN
    if (IS_VM_MEM(Addr))
      return(*(byte *)Addr);
    else
      return(*Addr & 0xff);
#else
    return(*(byte *)Addr);
#endif
  }
  else
  {
#if defined(BIG_ENDIAN) || !defined(ALLOW_NOT_ALIGNED_INT)
    if (IS_VM_MEM(Addr))
    {
      byte *B=(byte *)Addr;
      return GET_UINT32((uint)B[0]|((uint)B[1]<<8)|((uint)B[2]<<16)|((uint)B[3]<<24));
    }
    else
      return GET_UINT32(*Addr);
#else
    return GET_UINT32(*Addr);
#endif
  }
}

#if defined(BIG_ENDIAN) || !defined(ALLOW_NOT_ALIGNED_INT)
  #define GET_VALUE(ByteMode,Addr) GetValue(ByteMode,(uint *)Addr)
#else
  #define GET_VALUE(ByteMode,Addr) ((ByteMode) ? (*(byte *)(Addr)):GET_UINT32(*(uint *)(Addr)))
#endif


inline void RarVM::SetValue(bool ByteMode,uint *Addr,uint Value)
{
  if (ByteMode)
  {
#ifdef BIG_ENDIAN
    if (IS_VM_MEM(Addr))
      *(byte *)Addr=Value;
    else
      *Addr=(*Addr & ~0xff)|(Value & 0xff);
#else
    *(byte *)Addr=Value;
#endif
  }
  else
  {
#if defined(BIG_ENDIAN) || !defined(ALLOW_NOT_ALIGNED_INT) || !defined(PRESENT_INT32)
    if (IS_VM_MEM(Addr))
    {
      ((byte *)Addr)[0]=(byte)Value;
      ((byte *)Addr)[1]=(byte)(Value>>8);
      ((byte *)Addr)[2]=(byte)(Value>>16);
      ((byte *)Addr)[3]=(byte)(Value>>24);
    }
    else
      *(uint *)Addr=Value;
#else
    *(uint32 *)Addr=Value;
#endif
  }
}

#if defined(BIG_ENDIAN) || !defined(ALLOW_NOT_ALIGNED_INT) || !defined(PRESENT_INT32)
  #define SET_VALUE(ByteMode,Addr,Value) SetValue(ByteMode,(uint *)Addr,Value)
#else
  #define SET_VALUE(ByteMode,Addr,Value) ((ByteMode) ? (*(byte *)(Addr)=((byte)(Value))):(*(uint32 *)(Addr)=((uint32)(Value))))
#endif


void RarVM::SetLowEndianValue(uint *Addr,uint Value)
{
#if defined(BIG_ENDIAN) || !defined(ALLOW_NOT_ALIGNED_INT) || !defined(PRESENT_INT32)
  ((byte *)Addr)[0]=(byte)Value;
  ((byte *)Addr)[1]=(byte)(Value>>8);
  ((byte *)Addr)[2]=(byte)(Value>>16);
  ((byte *)Addr)[3]=(byte)(Value>>24);
#else
  *(uint32 *)Addr=Value;
#endif
}


inline uint* RarVM::GetOperand(VM_PreparedOperand *CmdOp)
{
  if (CmdOp->Type==VM_OPREGMEM)
    return((uint *)&Mem[(*CmdOp->Addr+CmdOp->Base)&VM_MEMMASK]);
  else
    return(CmdOp->Addr);
}


void RarVM::Execute(VM_PreparedProgram *Prg)
{
  memcpy(R,Prg->InitR,sizeof(Prg->InitR));
  size_t GlobalSize=Min(Prg->GlobalData.Size(),VM_GLOBALMEMSIZE);
  if (GlobalSize)
    memcpy(Mem+VM_GLOBALMEMADDR,&Prg->GlobalData[0],GlobalSize);
  size_t StaticSize=Min(Prg->StaticData.Size(),VM_GLOBALMEMSIZE-GlobalSize);
  if (StaticSize)
    memcpy(Mem+VM_GLOBALMEMADDR+GlobalSize,&Prg->StaticData[0],StaticSize);

  R[7]=VM_MEMSIZE;
  Flags=0;

  VM_PreparedCommand *PreparedCode=Prg->AltCmd ? Prg->AltCmd:&Prg->Cmd[0];
  if (Prg->CmdCount>0 && !ExecuteCode(PreparedCode,Prg->CmdCount))
  {
    // Invalid VM program. Let's replace it with 'return' command.
    PreparedCode[0].OpCode=VM_RET;
  }
  uint NewBlockPos=GET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x20])&VM_MEMMASK;
  uint NewBlockSize=GET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x1c])&VM_MEMMASK;
  if (NewBlockPos+NewBlockSize>=VM_MEMSIZE)
    NewBlockPos=NewBlockSize=0;
  Prg->FilteredData=Mem+NewBlockPos;
  Prg->FilteredDataSize=NewBlockSize;

  Prg->GlobalData.Reset();

  uint DataSize=Min(GET_VALUE(false,(uint*)&Mem[VM_GLOBALMEMADDR+0x30]),VM_GLOBALMEMSIZE-VM_FIXEDGLOBALSIZE);
  if (DataSize!=0)
  {
    Prg->GlobalData.Add(DataSize+VM_FIXEDGLOBALSIZE);
    memcpy(&Prg->GlobalData[0],&Mem[VM_GLOBALMEMADDR],DataSize+VM_FIXEDGLOBALSIZE);
  }
}


/*
Note:
  Due to performance considerations RAR VM may set VM_FS, VM_FC, VM_FZ
  incorrectly for byte operands. These flags are always valid only
  for 32-bit operands. Check implementation of concrete VM command
  to see if it sets flags right.
*/

#define SET_IP(IP)                      \
  if ((IP)>=CodeSize)                   \
    return(true);                       \
  if (--MaxOpCount<=0)                  \
    return(false);                      \
  Cmd=PreparedCode+(IP);

bool RarVM::ExecuteCode(VM_PreparedCommand *PreparedCode,uint CodeSize)
{
  int MaxOpCount=25000000;
  VM_PreparedCommand *Cmd=PreparedCode;
  while (1)
  {
#ifndef NORARVM
    // Get addresses to quickly access operands.
    uint *Op1=GetOperand(&Cmd->Op1);
    uint *Op2=GetOperand(&Cmd->Op2);
#endif
    switch(Cmd->OpCode)
    {
#ifndef NORARVM
      case VM_MOV:
        SET_VALUE(Cmd->ByteMode,Op1,GET_VALUE(Cmd->ByteMode,Op2));
        break;
#ifdef VM_OPTIMIZE
      case VM_MOVB:
        SET_VALUE(true,Op1,GET_VALUE(true,Op2));
        break;
      case VM_MOVD:
        SET_VALUE(false,Op1,GET_VALUE(false,Op2));
        break;
#endif
      case VM_CMP:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint Result=GET_UINT32(Value1-GET_VALUE(Cmd->ByteMode,Op2));
          Flags=Result==0 ? VM_FZ:(Result>Value1)|(Result&VM_FS);
        }
        break;
#ifdef VM_OPTIMIZE
      case VM_CMPB:
        {
          uint Value1=GET_VALUE(true,Op1);
          uint Result=GET_UINT32(Value1-GET_VALUE(true,Op2));
          Flags=Result==0 ? VM_FZ:(Result>Value1)|(Result&VM_FS);
        }
        break;
      case VM_CMPD:
        {
          uint Value1=GET_VALUE(false,Op1);
          uint Result=GET_UINT32(Value1-GET_VALUE(false,Op2));
          Flags=Result==0 ? VM_FZ:(Result>Value1)|(Result&VM_FS);
        }
        break;
#endif
      case VM_ADD:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint Result=GET_UINT32(Value1+GET_VALUE(Cmd->ByteMode,Op2));
          if (Cmd->ByteMode)
          {
            Result&=0xff;
            Flags=(Result<Value1)|(Result==0 ? VM_FZ:((Result&0x80) ? VM_FS:0));
          }
          else
            Flags=(Result<Value1)|(Result==0 ? VM_FZ:(Result&VM_FS));
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
#ifdef VM_OPTIMIZE
      case VM_ADDB:
        SET_VALUE(true,Op1,GET_VALUE(true,Op1)+GET_VALUE(true,Op2));
        break;
      case VM_ADDD:
        SET_VALUE(false,Op1,GET_VALUE(false,Op1)+GET_VALUE(false,Op2));
        break;
#endif
      case VM_SUB:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint Result=GET_UINT32(Value1-GET_VALUE(Cmd->ByteMode,Op2));
          Flags=Result==0 ? VM_FZ:(Result>Value1)|(Result&VM_FS);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
#ifdef VM_OPTIMIZE
      case VM_SUBB:
        SET_VALUE(true,Op1,GET_VALUE(true,Op1)-GET_VALUE(true,Op2));
        break;
      case VM_SUBD:
        SET_VALUE(false,Op1,GET_VALUE(false,Op1)-GET_VALUE(false,Op2));
        break;
#endif
      case VM_JZ:
        if ((Flags & VM_FZ)!=0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_JNZ:
        if ((Flags & VM_FZ)==0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_INC:
        {
          uint Result=GET_UINT32(GET_VALUE(Cmd->ByteMode,Op1)+1);
          if (Cmd->ByteMode)
            Result&=0xff;
          SET_VALUE(Cmd->ByteMode,Op1,Result);
          Flags=Result==0 ? VM_FZ:Result&VM_FS;
        }
        break;
#ifdef VM_OPTIMIZE
      case VM_INCB:
        SET_VALUE(true,Op1,GET_VALUE(true,Op1)+1);
        break;
      case VM_INCD:
        SET_VALUE(false,Op1,GET_VALUE(false,Op1)+1);
        break;
#endif
      case VM_DEC:
        {
          uint Result=GET_UINT32(GET_VALUE(Cmd->ByteMode,Op1)-1);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
          Flags=Result==0 ? VM_FZ:Result&VM_FS;
        }
        break;
#ifdef VM_OPTIMIZE
      case VM_DECB:
        SET_VALUE(true,Op1,GET_VALUE(true,Op1)-1);
        break;
      case VM_DECD:
        SET_VALUE(false,Op1,GET_VALUE(false,Op1)-1);
        break;
#endif
      case VM_JMP:
        SET_IP(GET_VALUE(false,Op1));
        continue;
      case VM_XOR:
        {
          uint Result=GET_UINT32(GET_VALUE(Cmd->ByteMode,Op1)^GET_VALUE(Cmd->ByteMode,Op2));
          Flags=Result==0 ? VM_FZ:Result&VM_FS;
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_AND:
        {
          uint Result=GET_UINT32(GET_VALUE(Cmd->ByteMode,Op1)&GET_VALUE(Cmd->ByteMode,Op2));
          Flags=Result==0 ? VM_FZ:Result&VM_FS;
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_OR:
        {
          uint Result=GET_UINT32(GET_VALUE(Cmd->ByteMode,Op1)|GET_VALUE(Cmd->ByteMode,Op2));
          Flags=Result==0 ? VM_FZ:Result&VM_FS;
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_TEST:
        {
          uint Result=GET_UINT32(GET_VALUE(Cmd->ByteMode,Op1)&GET_VALUE(Cmd->ByteMode,Op2));
          Flags=Result==0 ? VM_FZ:Result&VM_FS;
        }
        break;
      case VM_JS:
        if ((Flags & VM_FS)!=0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_JNS:
        if ((Flags & VM_FS)==0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_JB:
        if ((Flags & VM_FC)!=0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_JBE:
        if ((Flags & (VM_FC|VM_FZ))!=0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_JA:
        if ((Flags & (VM_FC|VM_FZ))==0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_JAE:
        if ((Flags & VM_FC)==0)
        {
          SET_IP(GET_VALUE(false,Op1));
          continue;
        }
        break;
      case VM_PUSH:
        R[7]-=4;
        SET_VALUE(false,(uint *)&Mem[R[7]&VM_MEMMASK],GET_VALUE(false,Op1));
        break;
      case VM_POP:
        SET_VALUE(false,Op1,GET_VALUE(false,(uint *)&Mem[R[7] & VM_MEMMASK]));
        R[7]+=4;
        break;
      case VM_CALL:
        R[7]-=4;
        SET_VALUE(false,(uint *)&Mem[R[7]&VM_MEMMASK],Cmd-PreparedCode+1);
        SET_IP(GET_VALUE(false,Op1));
        continue;
      case VM_NOT:
        SET_VALUE(Cmd->ByteMode,Op1,~GET_VALUE(Cmd->ByteMode,Op1));
        break;
      case VM_SHL:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint Value2=GET_VALUE(Cmd->ByteMode,Op2);
          uint Result=GET_UINT32(Value1<<Value2);
          Flags=(Result==0 ? VM_FZ:(Result&VM_FS))|((Value1<<(Value2-1))&0x80000000 ? VM_FC:0);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_SHR:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint Value2=GET_VALUE(Cmd->ByteMode,Op2);
          uint Result=GET_UINT32(Value1>>Value2);
          Flags=(Result==0 ? VM_FZ:(Result&VM_FS))|((Value1>>(Value2-1))&VM_FC);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_SAR:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint Value2=GET_VALUE(Cmd->ByteMode,Op2);
          uint Result=GET_UINT32(((int)Value1)>>Value2);
          Flags=(Result==0 ? VM_FZ:(Result&VM_FS))|((Value1>>(Value2-1))&VM_FC);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_NEG:
        {
          // We use "0-value" expression to suppress "unary minus to unsigned"
          // compiler warning.
          uint Result=GET_UINT32(0-GET_VALUE(Cmd->ByteMode,Op1));
          Flags=Result==0 ? VM_FZ:VM_FC|(Result&VM_FS);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
#ifdef VM_OPTIMIZE
      case VM_NEGB:
        SET_VALUE(true,Op1,0-GET_VALUE(true,Op1));
        break;
      case VM_NEGD:
        SET_VALUE(false,Op1,0-GET_VALUE(false,Op1));
        break;
#endif
      case VM_PUSHA:
        {
          const int RegCount=sizeof(R)/sizeof(R[0]);
          for (int I=0,SP=R[7]-4;I<RegCount;I++,SP-=4)
            SET_VALUE(false,(uint *)&Mem[SP & VM_MEMMASK],R[I]);
          R[7]-=RegCount*4;
        }
        break;
      case VM_POPA:
        {
          const int RegCount=sizeof(R)/sizeof(R[0]);
          for (uint I=0,SP=R[7];I<RegCount;I++,SP+=4)
            R[7-I]=GET_VALUE(false,(uint *)&Mem[SP & VM_MEMMASK]);
        }
        break;
      case VM_PUSHF:
        R[7]-=4;
        SET_VALUE(false,(uint *)&Mem[R[7]&VM_MEMMASK],Flags);
        break;
      case VM_POPF:
        Flags=GET_VALUE(false,(uint *)&Mem[R[7] & VM_MEMMASK]);
        R[7]+=4;
        break;
      case VM_MOVZX:
        SET_VALUE(false,Op1,GET_VALUE(true,Op2));
        break;
      case VM_MOVSX:
        SET_VALUE(false,Op1,(signed char)GET_VALUE(true,Op2));
        break;
      case VM_XCHG:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          SET_VALUE(Cmd->ByteMode,Op1,GET_VALUE(Cmd->ByteMode,Op2));
          SET_VALUE(Cmd->ByteMode,Op2,Value1);
        }
        break;
      case VM_MUL:
        {
          uint Result=GET_VALUE(Cmd->ByteMode,Op1)*GET_VALUE(Cmd->ByteMode,Op2);
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_DIV:
        {
          uint Divider=GET_VALUE(Cmd->ByteMode,Op2);
          if (Divider!=0)
          {
            uint Result=GET_VALUE(Cmd->ByteMode,Op1)/Divider;
            SET_VALUE(Cmd->ByteMode,Op1,Result);
          }
        }
        break;
      case VM_ADC:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint FC=(Flags&VM_FC);
          uint Result=GET_UINT32(Value1+GET_VALUE(Cmd->ByteMode,Op2)+FC);
          if (Cmd->ByteMode)
            Result&=0xff;
          Flags=(Result<Value1 || Result==Value1 && FC)|(Result==0 ? VM_FZ:(Result&VM_FS));
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
      case VM_SBB:
        {
          uint Value1=GET_VALUE(Cmd->ByteMode,Op1);
          uint FC=(Flags&VM_FC);
          uint Result=GET_UINT32(Value1-GET_VALUE(Cmd->ByteMode,Op2)-FC);
          if (Cmd->ByteMode)
            Result&=0xff;
          Flags=(Result>Value1 || Result==Value1 && FC)|(Result==0 ? VM_FZ:(Result&VM_FS));
          SET_VALUE(Cmd->ByteMode,Op1,Result);
        }
        break;
#endif  // for #ifndef NORARVM
      case VM_RET:
        if (R[7]>=VM_MEMSIZE)
          return(true);
        SET_IP(GET_VALUE(false,(uint *)&Mem[R[7] & VM_MEMMASK]));
        R[7]+=4;
        continue;
#ifdef VM_STANDARDFILTERS
      case VM_STANDARD:
        ExecuteStandardFilter((VM_StandardFilters)Cmd->Op1.Data);
        break;
#endif
      case VM_PRINT:
        break;
    }
    Cmd++;
    --MaxOpCount;
  }
}




void RarVM::Prepare(byte *Code,uint CodeSize,VM_PreparedProgram *Prg)
{
  InitBitInput();
  memcpy(InBuf,Code,Min(CodeSize,BitInput::MAX_SIZE));

  // Calculate the single byte XOR checksum to check validity of VM code.
  byte XorSum=0;
  for (uint I=1;I<CodeSize;I++)
    XorSum^=Code[I];

  faddbits(8);

  Prg->CmdCount=0;
  if (XorSum==Code[0]) // VM code is valid if equal.
  {
#ifdef VM_STANDARDFILTERS
    VM_StandardFilters FilterType=IsStandardFilter(Code,CodeSize);
    if (FilterType!=VMSF_NONE)
    {
      // VM code is found among standard filters.
      Prg->Cmd.Add(1);
      VM_PreparedCommand *CurCmd=&Prg->Cmd[Prg->CmdCount++];
      CurCmd->OpCode=VM_STANDARD;
      CurCmd->Op1.Data=FilterType;
      CurCmd->Op1.Addr=&CurCmd->Op1.Data;
      CurCmd->Op2.Addr=&CurCmd->Op2.Data;
      CurCmd->Op1.Type=CurCmd->Op2.Type=VM_OPNONE;
      CodeSize=0;
    }
#endif  
    uint DataFlag=fgetbits();
    faddbits(1);

    // Read static data contained in DB operators. This data cannot be
    // changed, it is a part of VM code, not a filter parameter.

    if (DataFlag&0x8000)
    {
      uint DataSize=ReadData(*this)+1;
      for (uint I=0;(uint)InAddr<CodeSize && I<DataSize;I++)
      {
        Prg->StaticData.Add(1);
        Prg->StaticData[I]=fgetbits()>>8;
        faddbits(8);
      }
    }

    while ((uint)InAddr<CodeSize)
    {
      Prg->Cmd.Add(1);
      VM_PreparedCommand *CurCmd=&Prg->Cmd[Prg->CmdCount];
      uint Data=fgetbits();
      if ((Data&0x8000)==0)
      {
        CurCmd->OpCode=(VM_Commands)(Data>>12);
        faddbits(4);
      }
      else
      {
        CurCmd->OpCode=(VM_Commands)((Data>>10)-24);
        faddbits(6);
      }
      if (VM_CmdFlags[CurCmd->OpCode] & VMCF_BYTEMODE)
      {
        CurCmd->ByteMode=(fgetbits()>>15)!=0;
        faddbits(1);
      }
      else
        CurCmd->ByteMode=0;
      CurCmd->Op1.Type=CurCmd->Op2.Type=VM_OPNONE;
      int OpNum=(VM_CmdFlags[CurCmd->OpCode] & VMCF_OPMASK);
      CurCmd->Op1.Addr=CurCmd->Op2.Addr=NULL;
      if (OpNum>0)
      {
        DecodeArg(CurCmd->Op1,CurCmd->ByteMode); // reading the first operand
        if (OpNum==2)
          DecodeArg(CurCmd->Op2,CurCmd->ByteMode); // reading the second operand
        else
        {
          if (CurCmd->Op1.Type==VM_OPINT && (VM_CmdFlags[CurCmd->OpCode]&(VMCF_JUMP|VMCF_PROC)))
          {
            // Calculating jump distance.
            int Distance=CurCmd->Op1.Data;
            if (Distance>=256)
              Distance-=256;
            else
            {
              if (Distance>=136)
                Distance-=264;
              else
                if (Distance>=16)
                  Distance-=8;
                else
                  if (Distance>=8)
                    Distance-=16;
              Distance+=Prg->CmdCount;
            }
            CurCmd->Op1.Data=Distance;
          }
        }
      }
      Prg->CmdCount++;
    }
  }

  // Adding RET command at the end of program.
  Prg->Cmd.Add(1);
  VM_PreparedCommand *CurCmd=&Prg->Cmd[Prg->CmdCount++];
  CurCmd->OpCode=VM_RET;
  CurCmd->Op1.Addr=&CurCmd->Op1.Data;
  CurCmd->Op2.Addr=&CurCmd->Op2.Data;
  CurCmd->Op1.Type=CurCmd->Op2.Type=VM_OPNONE;

  // If operand 'Addr' field has not been set by DecodeArg calls above,
  // let's set it to point to operand 'Data' field. It is necessary for
  // VM_OPINT type operands (usual integers) or maybe if something was 
  // not set properly for other operands. 'Addr' field is required
  // for quicker addressing of operand data.
  for (int I=0;I<Prg->CmdCount;I++)
  {
    VM_PreparedCommand *Cmd=&Prg->Cmd[I];
    if (Cmd->Op1.Addr==NULL)
      Cmd->Op1.Addr=&Cmd->Op1.Data;
    if (Cmd->Op2.Addr==NULL)
      Cmd->Op2.Addr=&Cmd->Op2.Data;
  }

#ifdef VM_OPTIMIZE
  if (CodeSize!=0)
    Optimize(Prg);
#endif
}


void RarVM::DecodeArg(VM_PreparedOperand &Op,bool ByteMode)
{
  uint Data=fgetbits();
  if (Data & 0x8000)
  {
    Op.Type=VM_OPREG;     // Operand is register (R[0]..R[7])
    Op.Data=(Data>>12)&7; // Register number
    Op.Addr=&R[Op.Data];  // Register address
    faddbits(4);          // 1 flag bit and 3 register number bits 
  }
  else
    if ((Data & 0xc000)==0)
    {
      Op.Type=VM_OPINT;   // Operand is integer
      if (ByteMode)
      {
        Op.Data=(Data>>6) & 0xff;  // Byte integer.
        faddbits(10);
      }
      else
      {
        faddbits(2);
        Op.Data=ReadData(*this);   // 32 bit integer.
      }
    }
    else
    {
      // Operand is data addressed by register data, base address or both.
      Op.Type=VM_OPREGMEM;
      if ((Data & 0x2000)==0)
      {
        // Base address is zero, just use the address from register.
        Op.Data=(Data>>10)&7;
        Op.Addr=&R[Op.Data];
        Op.Base=0;
        faddbits(6);
      }
      else
      {
        if ((Data & 0x1000)==0)
        {
          // Use both register and base address.
          Op.Data=(Data>>9)&7;
          Op.Addr=&R[Op.Data];
          faddbits(7);
        }
        else
        {
          // Use base address only. Access memory by fixed address.
          Op.Data=0;
          faddbits(4);
        }
        Op.Base=ReadData(*this); // Read base address.
      }
    }
}


uint RarVM::ReadData(BitInput &Inp)
{
  uint Data=Inp.fgetbits();
  switch(Data&0xc000)
  {
    case 0:
      Inp.faddbits(6);
      return((Data>>10)&0xf);
    case 0x4000:
      if ((Data&0x3c00)==0)
      {
        Data=0xffffff00|((Data>>2)&0xff);
        Inp.faddbits(14);
      }
      else
      {
        Data=(Data>>6)&0xff;
        Inp.faddbits(10);
      }
      return(Data);
    case 0x8000:
      Inp.faddbits(2);
      Data=Inp.fgetbits();
      Inp.faddbits(16);
      return(Data);
    default:
      Inp.faddbits(2);
      Data=(Inp.fgetbits()<<16);
      Inp.faddbits(16);
      Data|=Inp.fgetbits();
      Inp.faddbits(16);
      return(Data);
  }
}


void RarVM::SetMemory(uint Pos,byte *Data,uint DataSize)
{
  if (Pos<VM_MEMSIZE && Data!=Mem+Pos)
    memmove(Mem+Pos,Data,Min(DataSize,VM_MEMSIZE-Pos));
}


#ifdef VM_OPTIMIZE
void RarVM::Optimize(VM_PreparedProgram *Prg)
{
  VM_PreparedCommand *Code=&Prg->Cmd[0];
  uint CodeSize=Prg->CmdCount;

  for (uint I=0;I<CodeSize;I++)
  {
    VM_PreparedCommand *Cmd=Code+I;

    // Replace universal opcodes with faster byte or word only processing
    // opcodes.
    switch(Cmd->OpCode)
    {
      case VM_MOV:
        Cmd->OpCode=Cmd->ByteMode ? VM_MOVB:VM_MOVD;
        continue;
      case VM_CMP:
        Cmd->OpCode=Cmd->ByteMode ? VM_CMPB:VM_CMPD;
        continue;
    }
    if ((VM_CmdFlags[Cmd->OpCode] & VMCF_CHFLAGS)==0)
      continue;

    // If we do not have jump commands between the current operation
    // and next command which will modify processor flags, we can replace
    // the current command with faster version which does not need to
    // modify flags.
    bool FlagsRequired=false;
    for (uint J=I+1;J<CodeSize;J++)
    {
      int Flags=VM_CmdFlags[Code[J].OpCode];
      if (Flags & (VMCF_JUMP|VMCF_PROC|VMCF_USEFLAGS))
      {
        FlagsRequired=true;
        break;
      }
      if (Flags & VMCF_CHFLAGS)
        break;
    }

    // Below we'll replace universal opcodes with faster byte or word only 
    // processing opcodes, which also do not modify processor flags to
    // provide better performance.
    if (FlagsRequired)
      continue;
    switch(Cmd->OpCode)
    {
      case VM_ADD:
        Cmd->OpCode=Cmd->ByteMode ? VM_ADDB:VM_ADDD;
        continue;
      case VM_SUB:
        Cmd->OpCode=Cmd->ByteMode ? VM_SUBB:VM_SUBD;
        continue;
      case VM_INC:
        Cmd->OpCode=Cmd->ByteMode ? VM_INCB:VM_INCD;
        continue;
      case VM_DEC:
        Cmd->OpCode=Cmd->ByteMode ? VM_DECB:VM_DECD;
        continue;
      case VM_NEG:
        Cmd->OpCode=Cmd->ByteMode ? VM_NEGB:VM_NEGD;
        continue;
    }
  }
}
#endif


#ifdef VM_STANDARDFILTERS
VM_StandardFilters RarVM::IsStandardFilter(byte *Code,uint CodeSize)
{
  struct StandardFilterSignature
  {
    int Length;
    uint CRC;
    VM_StandardFilters Type;
  } static StdList[]={
    53, 0xad576887, VMSF_E8,
    57, 0x3cd7e57e, VMSF_E8E9,
   120, 0x3769893f, VMSF_ITANIUM,
    29, 0x0e06077d, VMSF_DELTA,
   149, 0x1c2c5dc8, VMSF_RGB,
   216, 0xbc85e701, VMSF_AUDIO,
    40, 0x46b9c560, VMSF_UPCASE
  };
  uint CodeCRC=CRC(0xffffffff,Code,CodeSize)^0xffffffff;
  for (uint I=0;I<ASIZE(StdList);I++)
    if (StdList[I].CRC==CodeCRC && StdList[I].Length==CodeSize)
      return(StdList[I].Type);
  return(VMSF_NONE);
}


void RarVM::ExecuteStandardFilter(VM_StandardFilters FilterType)
{
  switch(FilterType)
  {
    case VMSF_E8:
    case VMSF_E8E9:
      {
        byte *Data=Mem;
        int DataSize=R[4];
        uint FileOffset=R[6];

        if ((uint)DataSize>=VM_GLOBALMEMADDR || DataSize<4)
          break;

        const int FileSize=0x1000000;
        byte CmpByte2=FilterType==VMSF_E8E9 ? 0xe9:0xe8;
        for (int CurPos=0;CurPos<DataSize-4;)
        {
          byte CurByte=*(Data++);
          CurPos++;
          if (CurByte==0xe8 || CurByte==CmpByte2)
          {
#ifdef PRESENT_INT32
            int32 Offset=CurPos+FileOffset;
            int32 Addr=GET_VALUE(false,Data);
            if (Addr<0)
            {
              if (Addr+Offset>=0)
                SET_VALUE(false,Data,Addr+FileSize);
            }
            else
              if (Addr<FileSize)
                SET_VALUE(false,Data,Addr-Offset);
#else
            long Offset=CurPos+FileOffset;
            long Addr=GET_VALUE(false,Data);
            if ((Addr & 0x80000000)!=0)
            {
              if (((Addr+Offset) & 0x80000000)==0)
                SET_VALUE(false,Data,Addr+FileSize);
            }
            else 
              if (((Addr-FileSize) & 0x80000000)!=0)
                SET_VALUE(false,Data,Addr-Offset);
#endif
            Data+=4;
            CurPos+=4;
          }
        }
      }
      break;
    case VMSF_ITANIUM:
      {
        byte *Data=Mem;
        int DataSize=R[4];
        uint FileOffset=R[6];

        if ((uint)DataSize>=VM_GLOBALMEMADDR || DataSize<21)
          break;

        int CurPos=0;

        FileOffset>>=4;

        while (CurPos<DataSize-21)
        {
          int Byte=(Data[0]&0x1f)-0x10;
          if (Byte>=0)
          {
            static byte Masks[16]={4,4,6,6,0,0,7,7,4,4,0,0,4,4,0,0};
            byte CmdMask=Masks[Byte];
            if (CmdMask!=0)
              for (int I=0;I<=2;I++)
                if (CmdMask & (1<<I))
                {
                  int StartPos=I*41+5;
                  int OpType=FilterItanium_GetBits(Data,StartPos+37,4);
                  if (OpType==5)
                  {
                    int Offset=FilterItanium_GetBits(Data,StartPos+13,20);
                    FilterItanium_SetBits(Data,(Offset-FileOffset)&0xfffff,StartPos+13,20);
                  }
                }
          }
          Data+=16;
          CurPos+=16;
          FileOffset++;
        }
      }
      break;
    case VMSF_DELTA:
      {
        int DataSize=R[4],Channels=R[0],SrcPos=0,Border=DataSize*2;
        SET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x20],DataSize);
        if ((uint)DataSize>=VM_GLOBALMEMADDR/2)
          break;

        // Bytes from same channels are grouped to continual data blocks,
        // so we need to place them back to their interleaving positions.
        for (int CurChannel=0;CurChannel<Channels;CurChannel++)
        {
          byte PrevByte=0;
          for (int DestPos=DataSize+CurChannel;DestPos<Border;DestPos+=Channels)
            Mem[DestPos]=(PrevByte-=Mem[SrcPos++]);
        }
      }
      break;
    case VMSF_RGB:
      {
        int DataSize=R[4],Width=R[0]-3,PosR=R[1];
        byte *SrcData=Mem,*DestData=SrcData+DataSize;
        const int Channels=3;
        SET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x20],DataSize);
        if ((uint)DataSize>=VM_GLOBALMEMADDR/2 || PosR<0)
          break;
        for (int CurChannel=0;CurChannel<Channels;CurChannel++)
        {
          uint PrevByte=0;

          for (int I=CurChannel;I<DataSize;I+=Channels)
          {
            uint Predicted;
            int UpperPos=I-Width;
            if (UpperPos>=3)
            {
              byte *UpperData=DestData+UpperPos;
              uint UpperByte=*UpperData;
              uint UpperLeftByte=*(UpperData-3);
              Predicted=PrevByte+UpperByte-UpperLeftByte;
              int pa=abs((int)(Predicted-PrevByte));
              int pb=abs((int)(Predicted-UpperByte));
              int pc=abs((int)(Predicted-UpperLeftByte));
              if (pa<=pb && pa<=pc)
                Predicted=PrevByte;
              else
                if (pb<=pc)
                  Predicted=UpperByte;
                else
                  Predicted=UpperLeftByte;
            }
            else
              Predicted=PrevByte;
            DestData[I]=PrevByte=(byte)(Predicted-*(SrcData++));
          }
        }
        for (int I=PosR,Border=DataSize-2;I<Border;I+=3)
        {
          byte G=DestData[I+1];
          DestData[I]+=G;
          DestData[I+2]+=G;
        }
      }
      break;
    case VMSF_AUDIO:
      {
        int DataSize=R[4],Channels=R[0];
        byte *SrcData=Mem,*DestData=SrcData+DataSize;
        SET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x20],DataSize);
        if ((uint)DataSize>=VM_GLOBALMEMADDR/2)
          break;
        for (int CurChannel=0;CurChannel<Channels;CurChannel++)
        {
          uint PrevByte=0,PrevDelta=0,Dif[7];
          int D1=0,D2=0,D3;
          int K1=0,K2=0,K3=0;
          memset(Dif,0,sizeof(Dif));

          for (int I=CurChannel,ByteCount=0;I<DataSize;I+=Channels,ByteCount++)
          {
            D3=D2;
            D2=PrevDelta-D1;
            D1=PrevDelta;

            uint Predicted=8*PrevByte+K1*D1+K2*D2+K3*D3;
            Predicted=(Predicted>>3) & 0xff;

            uint CurByte=*(SrcData++);

            Predicted-=CurByte;
            DestData[I]=Predicted;
            PrevDelta=(signed char)(Predicted-PrevByte);
            PrevByte=Predicted;

            int D=((signed char)CurByte)<<3;

            Dif[0]+=abs(D);
            Dif[1]+=abs(D-D1);
            Dif[2]+=abs(D+D1);
            Dif[3]+=abs(D-D2);
            Dif[4]+=abs(D+D2);
            Dif[5]+=abs(D-D3);
            Dif[6]+=abs(D+D3);

            if ((ByteCount & 0x1f)==0)
            {
              uint MinDif=Dif[0],NumMinDif=0;
              Dif[0]=0;
              for (int J=1;J<sizeof(Dif)/sizeof(Dif[0]);J++)
              {
                if (Dif[J]<MinDif)
                {
                  MinDif=Dif[J];
                  NumMinDif=J;
                }
                Dif[J]=0;
              }
              switch(NumMinDif)
              {
                case 1: if (K1>=-16) K1--; break;
                case 2: if (K1 < 16) K1++; break;
                case 3: if (K2>=-16) K2--; break;
                case 4: if (K2 < 16) K2++; break;
                case 5: if (K3>=-16) K3--; break;
                case 6: if (K3 < 16) K3++; break;
              }
            }
          }
        }
      }
      break;
    case VMSF_UPCASE:
      {
        int DataSize=R[4],SrcPos=0,DestPos=DataSize;
        if ((uint)DataSize>=VM_GLOBALMEMADDR/2)
          break;
        while (SrcPos<DataSize)
        {
          byte CurByte=Mem[SrcPos++];
          if (CurByte==2 && (CurByte=Mem[SrcPos++])!=2)
            CurByte-=32;
          Mem[DestPos++]=CurByte;
        }
        SET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x1c],DestPos-DataSize);
        SET_VALUE(false,&Mem[VM_GLOBALMEMADDR+0x20],DataSize);
      }
      break;
  }
}


uint RarVM::FilterItanium_GetBits(byte *Data,int BitPos,int BitCount)
{
  int InAddr=BitPos/8;
  int InBit=BitPos&7;
  uint BitField=(uint)Data[InAddr++];
  BitField|=(uint)Data[InAddr++] << 8;
  BitField|=(uint)Data[InAddr++] << 16;
  BitField|=(uint)Data[InAddr] << 24;
  BitField >>= InBit;
  return(BitField & (0xffffffff>>(32-BitCount)));
}


void RarVM::FilterItanium_SetBits(byte *Data,uint BitField,int BitPos,int BitCount)
{
  int InAddr=BitPos/8;
  int InBit=BitPos&7;
  uint AndMask=0xffffffff>>(32-BitCount);
  AndMask=~(AndMask<<InBit);

  BitField<<=InBit;

  for (uint I=0;I<4;I++)
  {
    Data[InAddr+I]&=AndMask;
    Data[InAddr+I]|=BitField;
    AndMask=(AndMask>>8)|0xff000000;
    BitField>>=8;
  }
}
#endif
