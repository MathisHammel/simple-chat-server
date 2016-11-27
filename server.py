from multiprocessing import Process, Queue, Manager, Array
import time
import socket
import sys
from multiprocessing.reduction import ForkingPickler
import StringIO
import pickle
import os
import signal

VERBOSITY=5 #1=info 2=info+ 3=debug
DELAY=0 #Slow requests processing time

SERVER_IP='46.101.193.203'
SERVER_PORT=int(sys.argv[1])

def forking_dumps(obj):
    buf = StringIO.StringIO()
    ForkingPickler(buf).dump(obj)
    return buf.getvalue()

def printv(string, lvl):
    if lvl<=VERBOSITY:
        print string

def getLines(socketObject, nLines, init=''):
    while init.count('\n')<nLines:
        init+=socketObject.recv(1024)
    return init

def serverProcess(q,threadId,status,chatRooms,roomIds,activeConnections):
    printv('Started thread '+str(threadId),2)
    while True:
        try:
            qelt=q.get()
            conn,addr=pickle.loads(qelt)
            status[threadId]=True
            data = conn.recv(4096)
            if DELAY>0:
                printv('Waiting '+str(DELAY)+'s',3)
                time.sleep(DELAY)
            if not data:
                conn.close()
                printv('No data received from'+str(addr),2)
                continue
            lines=[]
            if data.startswith('HELO '):
                text=data[5:].strip()
                conn.sendall('HELO '+text+'\nIP:'+conn.getsockname()[0]+'\nPort:'+sys.argv[1]+'\nStudentID:16313441\n')
            if data.startswith('JOIN_CHATROOM'):
                data=getLines(conn,4,data)
                printv(data,3)
                lines=data.strip().split('\n')
            printv(str(lines),3)
            if lines[0].startswith('JOIN_CHATROOM: ') and lines[1].startswith('CLIENT_IP: ') and lines[2].startswith('PORT: ') and lines[3].startswith('CLIENT_NAME: '):
                nick=lines[3][len('CLIENT_NAME: '):]
                room=lines[0][len('JOIN_CHATROOM: '):]
                if room not in roomIds:
                    roomIds[room]=roomIds['nextId']
                    roomIds['nextId']+=1
                roomId=roomIds[room]
                if roomId not in chatRooms:
                    chatRooms[roomId]={'name':room,'clients':{},'nextId':0}
                for clientId in chatRooms[roomId]['clients']:
                    cliConn, cliAddr = pickle.loads(chatRooms[room]['clients'][clientId]['socketObject'])
                    cliConn.sendall(nick+' has joined this chatroom.\n')
                    printv('Sent login message to '+str(cliAddr),3)
                cliId=chatRooms[roomId]['nextId']
                print chatRooms[roomId]['nextId']
                chatRooms[roomId]['nextId']+=1
                print chatRooms[roomId]['nextId']
                chatRooms[roomId]['clients'][cliId]={'nick':nick, 'socketObject':qelt}
                printv('Room : '+str(chatRooms[roomId]),3)
                conn.sendall('JOINED_CHATROOM: '+room+'\nSERVER_IP: '+SERVER_IP+'\nPORT: '+str(SERVER_PORT)+'\nROOM_REF: '+str(roomIds[room])+'\nJOIN_ID: '+str(cliId)+'\n')
                activeConnections[qelt]=True
                q.put(qelt)

            if data.startswith('LEAVE_CHATROOM'):
                data=getLines(conn,3,data)
                printv(data,3)
                lines=data.strip().split()
            if lines[0].startswith('LEAVE_CHATROOM: ') and lines[1].startswith('JOIN_ID: ') and lines[2].startswith('CLIENT_NAME: '):
                room=lines[0][len('LEAVE_CHATROOM: '):]
                clientId=int(lines[1][len('JOIN_ID: '):])
                nick=lines[2][len('CLIENT_NAME: '):]
                roomId=roomIds[room]
                if clientId in chatRooms[roomId]['clients']:
                    del chatRooms[roomId]['clients'][clientId]
                    for client in chatRooms[roomId]['clients']:
                        cliConn, cliAddr = pickle.loads(chatRooms[room]['clients'][client]['socketObject'])
                        cliConn.sendall(nick+' has left this chatroom.\n')
                conn.sendall('LEFT_CHATROOM: '+room+'\nJOIN_ID: '+clientId+'\n')
                q.put(qelt)
            if data.startswith('DISCONNECT'):
                data=getLines(conn,3,data)
                printv(data,3)
                lines=data.strip().split()
            if lines[0].startswith('DISCONNECT: ') and lines[1].startswith('PORT: ') and lines[2].startswith('CLIENT_NAME: '):
                clientName=lines[2][len('CLIENT_NAME: '):]
                for room in chatRooms: #could be optimized a bit, complexity is O(Nrooms*Nclientsperroom) but could be O(NroomsOfDisconnectingClient)
                    for cli in chatRooms[room]['clients']:
                        if chatRooms[room]['clients'][cli]['nick']==clientName:
                            del chatRooms[room]['clients'][cli]
                conn.close()
            if data.startswith('CHAT'):
                while not data.endswith('\n\n'):
                    data+=conn.recv(1024)
                printv(data,3)
                lines=data.strip().split()
            if lines[0].startswith('CHAT: ') and lines[1].startwith('JOIN_ID: ') and lines[2].startswith('CLIENT_NAME: ') and lines[3].startswith('MESSAGE: '):
                roomId=lines[0][len('CHAT: '):]
                clientId=lines[1][len('JOIN_ID: '):]
                clientNick=lines[2][len('CLIENT_NAME: '):]
                message=[lines[3][len('MESSAGE: '):]]
                for line in lines[4:]:
                    message.append(line)
                for client in chatRooms[roomId]['clients']:
                    cliConn, cliAddr = pickle.loads(chatRooms[room]['clients'][clientId]['socketObject'])
                    cliCon.sendall('CHAT: '+roomId+'\nCLIENT_NAME: '+clientNick+'\nMESSAGE: ')
                    for messageLine in message:
                        cliCon.sendall(messageLine+'\n')
                q.put(qelt)
                
        except KeyboardInterrupt:
            printv('Thread '+str(threadId)+' stopped',3)
            sys.exit(0)
        except socket.error:
            printv('Socket error',1)
        except Exception as e:
            printv('Thread failure',1)
            printv(str(e),2)
            sys.exit(0)
        finally:
            status[threadId]=False

def terminationHandler(_signo, _stack_frame):
    printv('Received KILL_SERVICE',1)
    global threadPool
    for thr in threadPool:
        thr.terminate()

if __name__ == '__main__':
    if len(sys.argv)<3:
        print 'Usage : python2 server.py port numThreads'
        sys.exit(0)
    s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    maxThreadNum=int(sys.argv[2])
    minThreadNum=max(1,int(sys.argv[2])/2)
    try :  #Server setup
        global threadPool
        q=Queue()
	manager=Manager()
        threadStatus=manager.list()
        chatRooms=manager.dict()
        roomIds=manager.dict()
        roomIds['nextId']=0
        activeConnections=manager.dict()
        threadPool=[]
	for pstart in range(int(sys.argv[2])):
            threadStatus.append(False)
            p=Process(target=serverProcess, args=(q,pstart,threadStatus,chatRooms,roomIds,activeConnections))
            p.start()
            threadPool.append(p)
        printv('All threads started',1)
        signal.signal(signal.SIGTERM,terminationHandler)
        HOST='0.0.0.0'
        PORT=int(sys.argv[1])
        s.bind((HOST,PORT))
        s.listen(1)
        s.settimeout(10)
        printv('Server started',1)
    except Exception as e:
        print 'Could not start server.'
        printv(e,2)
        for thr in threadPool:
            thr.terminate()
        sys.exit(0)
            
    while True:  #Master loop
        try:
            conn, addr = s.accept()
            printv('[Master] New connection from'+str(addr),3)
            if q.empty() and len(threadPool)>minThreadNum:
                if threadStatus[-1]==False:
                    threadPool[-1].terminate()
                    threadPool.pop()
                    threadStatus.pop()
                    printv('Killed thread. New thread count : '+str(len(threadPool)),2)
            if q.qsize()>2 and len(threadPool)<maxThreadNum:
                threadStatus.append(False)
                p=Process(target=serverProcess, args=(q,len(threadPool),threadStatus,))
                threadPool.append(p)
                p.start()
                printv('Started thread. New thread count : '+str(len(threadPool)),2)
            q.put(forking_dumps([conn,addr]))
            conn.close()
        except KeyboardInterrupt:
            printv('Server stopped from keyboard',1)
            sys.exit(0)
        except socket.timeout:
            pass
