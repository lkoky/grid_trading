#!/bin/sh
INST_DIR=`pwd`
LOG_FILE="logs/run.log" 
# 检查LOG_FILE路径是否存在，不存在则创建目录
LOG_DIR=$(dirname "$LOG_FILE")
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi
SERVICE=`pwd | awk -F/ '{print $4}'`

killadapter()
{
    # list pids of the iread processes
    pids=`ps -ef | grep ${INST_DIR} | grep -v "grep"| grep -v "server.sh"  | awk '{print $2}'`
    if [ -n "$pids" ]; then
         echo "kill pid=$pids"
          kill -9 $pids
    else
        echo "Server process does not exist!"
        echo "Server process does not exist!" >>${LOG_FILE}
    fi
}


start() 
{ 
    # list pids of the iread processes 
    pids=`ps -ef | grep ${INST_DIR} | grep -v "grep" | grep -v "server.sh" | awk '{print $2}'`
    if [ -n "$pids" ]; then 
       echo "$SERVICE already running. pid=$pids " 
       echo "$SERVICE already running." >>${LOG_FILE} 
       exit 0 
    fi 
    if [ -e ${LOG_FILE} ]; then 
        mv ${LOG_FILE} ${LOG_FILE}.bak 
    fi 
    echo "starting $SERVICE at: `date`" 
    echo "starting $SERVICE at: `date`" >>${LOG_FILE} 
    cd ${INST_DIR} 
    
    # 创建虚拟空间
    python3 -m venv .venv
    # 使用虚拟空间启动
    source .venv/bin/activate 
    nohup python -u grid_trading_service.py > ${LOG_FILE} 2>&1 &
    
    # ./bin/startup.sh 2>&1 >>${LOG_FILE} & 

    sleep 2
    pids=`ps -ef | grep ${INST_DIR} | grep -v "grep" | grep -v "server.sh" | awk '{print $2}'`
    echo "pid=$pids"
    tail -f ${LOG_FILE}    
} 

stop() 
{ 
     echo "stopping $SERVICE at: `date`" 
     echo "stopping $SERVICE at: `date`">>${LOG_FILE} 
     killadapter 
} 


status() 
{ 
    # list pids of the iread processes 
    pids=`ps -ef | grep ${INST_DIR} | grep -v "grep" | grep -v "server.sh" | awk '{print $2}'` 

    if [ -n "$pids" ]; then 
        echo "$SERVICE is running. pid=$pids" 
        echo "$SERVICE is running" >>${LOG_FILE} 
              exit 0 
    fi 
    echo $SERVICE is stopped 
    exit 3 
} 


restart() 
{ 
    stop 
    sleep 1 
    start 
} 

case "$1" in 
  start) 
        start 
        ;; 
  stop) 
        stop 
        ;; 
  restart) 
        restart 
        ;; 
  status) 
        status 
        ;; 
        -h|-help|--h|--help|help) 
        echo "Usage: $SCRIPT_NAME {start|stop|restart|status|-h|-help|--help|help}" 
        exit 0 
        ;; 
  *) 
        echo "Usage: $SCRIPT_NAME {start|stop|restart|status|-h|-help|--help|help}" 
        exit 1 
esac 

exit 0  
