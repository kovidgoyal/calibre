'''
class Timer:
  def __init__(self):
    self.start = time.time()
  def restart(self):
    self.start = time.time()
  def get_time_hhmmss(self):
    end = time.time()
    m, s = divmod(end - self.start, 60)
    h, m = divmod(m, 60)
    time_str = "%02d:%02d:%02d" % (h, m, s)
    return time_str
  def timereach(self):
    while Timer.get_time_hhmmss=Timer.get_time_hhmmss(hour,minute,0):
      from timeit import default_timer as timer
'''
#input hour and min return sth when completed#
from timeit import default_timer as timer
hour, minute=input('Hours, Minute=').split()
hour=hour.strip(',')
neededtime=int(hour)*3600+int(minute)*60
elapsed_time=0
start = timer()
while elapsed_time<=neededtime:
  elapsed_time = timer() - start
else:
  print('OK',hour,'hours and ',minute,'minutes has passed')
