# 发布脚本说明
fab prod:q-app-web,branch=master start

fab prod:q-app-web,branch=master,profile=xxx start

fab prod:q-app-web,branch=master,is_pack=false,profile=xxx start



fab rollback:prod,module=q-app-web,v=180326134415 start

fab rollback:prod,module=q-app-web,v=180326134415,profile=xxx start