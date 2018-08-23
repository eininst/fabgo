# 发布脚本说明
fab prod:mp,branch=master go #发布go程序

fab prod:mp,branch=master n #发布nginx

fab prod:mp,branch=master ngo 发布go和nginx


fab rollback:prod,module=mp,v=180326134415 go