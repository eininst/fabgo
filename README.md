# 发布脚本说明
fab prod:mp,branch=master go

fab prod:mp,branch=master n

fab prod:mp,branch=master ngo



fab rollback:prod,module=q-app-web,v=180326134415 start

fab rollback:prod,module=q-app-web,v=180326134415,profile=xxx start