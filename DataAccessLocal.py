import os
from datetime import datetime, time

class dataAccess(object):


    def __init__(self):
        self.working_directory = os.getcwd()


    def getDigest(self, fileName):
        self.sig_path = '%s/%s' % (self.working_directory, fileName)
        last_signature = open(self.sig_path, "r")
        old_sig = last_signature.readline()
        last_signature.close()
        return old_sig


    def replaceDigest(self, sig):
        new_sig = open(self.sig_path, "w")
        new_sig.write(sig)
        new_sig.close()


    def logRun(self, output):
        logfile = open("%s/run_log.txt" % self.working_directory, "a")
        logfile.write(output)
        logfile.close()