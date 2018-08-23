

s = 'echo "{0}"'.format("ps -ef|grep %s/%s |grep -v 'grep' |awk '{print $2}'" % (1,2))

print s