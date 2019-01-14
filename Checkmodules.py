'''
Keys are needed to be imported from another files
We needed blocked exit.
Fixed short answers.

'''
'''
Objectives:
-Make a basic(crappy) checking system.(Done)
-When percent is good 50+ allows exits.
-If not reach retries can be done as like nothing happened.
'''
key=(1,2,3)#type tuple this is dummy key. Must be imported.
AllowQuit=False
point=0
for i in range(key):
    answer=input()
    if answer==key[i]:
        point+=1
Percent=point/len(key)*100
print(Percent)
if Percent>50:
    AllowQuit=True