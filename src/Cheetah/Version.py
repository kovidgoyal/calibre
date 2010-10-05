Version = '2.4.3'
VersionTuple = (2, 4, 3, 'development', 0)

MinCompatibleVersion = '2.0rc6'
MinCompatibleVersionTuple = (2, 0, 0, 'candidate', 6)

####
def convertVersionStringToTuple(s):
    versionNum = [0, 0, 0]
    releaseType = 'final'
    releaseTypeSubNum = 0
    if s.find('a')!=-1:
        num, releaseTypeSubNum = s.split('a')
        releaseType = 'alpha'
    elif s.find('b')!=-1:
        num, releaseTypeSubNum = s.split('b')
        releaseType = 'beta'
    elif s.find('rc')!=-1:
        num, releaseTypeSubNum = s.split('rc')
        releaseType = 'candidate'
    else:
        num = s
    num = num.split('.')
    for i in range(len(num)):
        versionNum[i] = int(num[i])
    if len(versionNum)<3:
        versionNum += [0]
    releaseTypeSubNum = int(releaseTypeSubNum)

    return tuple(versionNum+[releaseType, releaseTypeSubNum])


if __name__ == '__main__':
    c = convertVersionStringToTuple
    print(c('2.0a1'))
    print(c('2.0b1'))
    print(c('2.0rc1'))
    print(c('2.0'))
    print(c('2.0.2'))


    assert c('0.9.19b1') < c('0.9.19')
    assert c('0.9b1') < c('0.9.19')

    assert c('2.0a2') > c('2.0a1')
    assert c('2.0b1') > c('2.0a2')
    assert c('2.0b2') > c('2.0b1')
    assert c('2.0b2') == c('2.0b2')

    assert c('2.0rc1') > c('2.0b1')
    assert c('2.0rc2') > c('2.0rc1')
    assert c('2.0rc2') > c('2.0b1')

    assert c('2.0') > c('2.0a1')
    assert c('2.0') > c('2.0b1')
    assert c('2.0') > c('2.0rc1')
    assert c('2.0.1') > c('2.0')
    assert c('2.0rc1') > c('2.0b1')
