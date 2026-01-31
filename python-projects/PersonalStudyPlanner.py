
name = ""
subjects = []
subjectsBfProcessing = ''
totalStudyTime = 0



def getName():
    name = input("enter your name") 
    return name

def getSubjects():
    subjectsBfProcessing = input("enter your subjects, seperated by a comma please")
    return subjectsBfProcessing

def getStudyTime():
    totalStudyTime = int(input("enter the total time you want to study please"))
    return totalStudyTime


def checkValidity(name, subjectsBfProcessing, totalStudyTime):
    if name.isdigit():
        print("not a valid name")
        name = getName()

    if "," not in subjectsBfProcessing:
        print("not a valid list of subjects, no commas to separate")
        subjectsBfProcessing = getSubjects()

    # This check is unnecessary because getStudyTime already returns int,
    # but keeping your idea:
    if not isinstance(totalStudyTime, int):
        print("not a valid study time, its not a number")
        totalStudyTime = getStudyTime()

    return name, subjectsBfProcessing, totalStudyTime


def main():
    name = getName()
    subjectsBfProcessing = getSubjects()
    totalStudyTime = getStudyTime()

    name, subjectsBfProcessing, totalStudyTime = checkValidity(
        name, subjectsBfProcessing, totalStudyTime
    )

    subjects = [s.strip() for s in subjectsBfProcessing.split(",") if s.strip()]
    print(subjects)

main()

