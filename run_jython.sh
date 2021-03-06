#
# To run in jython make sure that  you have
# * the genlib/python folder in your $JYTHONPATH (just like you would with C-python)
# * a JDBC postgres driver in your $CLASSPATH
#
# Also, all the standard crawl dependencies apply, which can all be installed with a 
# jython easy_install, with one exception : you need to install a CherryPy-3.2.0rc1 
# at the very least, because there is a bug in the 3.1 version that causes exceptuions 
# when trying to access threading properties. 
# 

export CLASSPATH=./lib/postgresql-8.4-701.jdbc4.jar
export CLASSPATH=${CLASSPATH}:./lib/sam-1.27.jar
export CLASSPATH=${CLASSPATH}:./lib/crawl.jar
export CLASSPATH=${CLASSPATH}:./lib/log4j.jar

jython -Dlogfolder=./tmp run.py -c ini/config.py -l ini/logging.ini #-p ./tmp/pid -d -t

