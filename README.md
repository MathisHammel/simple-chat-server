server.py implements a simple chat server over TCP. 
No dependencies except builtin python2.
Usage : python2 server.py port numThreads

Made by Mathis HAMMEL (16313441) for Trinity College Dublin module CS4032.

WARNING : The usage of managed dictionaries in python2 multiprocessing is highly unstable. For most systems the shared dictionaries won't work, making this server useless. 
To see if this works on your system, the server should print 0 then 1 after the first login. If it prints 0 then 0, the server will not work properly.