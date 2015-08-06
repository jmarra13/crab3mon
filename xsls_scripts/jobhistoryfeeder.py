import os
import classad
import htcondor
import subprocess
from pprint import pprint
from socket import gethostname
from datetime import date, datetime
from xml.etree.ElementTree import Element, SubElement, tostring


fmt = "%Y-%m-%dT%H:%M:%S%z"

# since ES search is hosted at CERN
# we should set timezone to Europe/Zurich
# otherwise the publication will fail due
# timezone difference 

os.environ['TZ'] = "Europe/Zurich"

class jobHistoryFeed(object):
    def __init__(self, perJobHistoryDir):
        self.filesToParse = []
        self.today = date.today()
        self.totalParsed = 0
        self.perJobHistoryDir = perJobHistoryDir

    def isRunable(self):
        XML_DIR = '/tmp/xmldir'
        PER_JOB_HISTORY_DIR = self.runCondorConfigVal(self.perJobHistoryDir)
        if PER_JOB_HISTORY_DIR == '':
            return False
    
        if not os.path.exists(PER_JOB_HISTORY_DIR):
            print("%s does not exist." % PER_JOB_HISTORY_DIR)
            return False
    
        if not os.path.exists(XML_DIR):
            try:
                os.makedirs(XML_DIR)
            except:
                print("Error creating the tmp dir. Exiting")
                return False
                    
        self.XML_DIR = XML_DIR
        self.PER_JOB_HISTORY_DIR = PER_JOB_HISTORY_DIR
        self.xmlBuffer = {}
        return True
        
    def getFilesToParse(self):
        #listing the files which are older than 1 day
        old_files = []
        for root, dirs, files in os.walk(self.PER_JOB_HISTORY_DIR):
            for name in files:
                filedate = date.fromtimestamp(os.path.getmtime(os.path.join(root, name)))
                if (self.today - filedate).days > 1: # file is older than 1 day                                         
                    old_files.append(name)
        self.filesToParse = old_files
        return len(old_files)

    def writeXMLToFile(self, xml_data):
        try:
           xml_file = os.path.join(self.XML_DIR, str(xml_data['ClusterId']) + '.xml')
        except Exception, e:
           pprint("failed to create XML file for %s - possible reason: no ClusterId classAds")
           pprint(str(e))
           exit()

        # prepare the XML doc
        root = Element('serviceupdate')
        root.set( "xmlns",  "http://sls.cern.ch/SLS/XML/update")
        child = SubElement(root, "id")
        nameId = xml_data['GlobalJobId'].split('#')[0]
        nameId = nameId.replace('@','-')
        child.text = nameId 
    
        now_utc = datetime.now().strftime(fmt)
        child_timestamp = SubElement(root, "timestamp")
        child_timestamp.text = str(now_utc)
        child_availability = SubElement(root, "availability")
        child_availability.text = "100"
        # extra availability info
        child_availabilitydesc = SubElement(root,"availabilitydesc")
        child_availabilitydesc.text = "CRAB3 Schedd Availability"
        child_contact = SubElement(root,"contact")
        child_contact.text = "cms-service-crab3htcondor-admins@cern.ch"
        #child_webpage = SubElement(root,"webpage")
        #child_webpage.text = "http://%s
        data = SubElement(root, "data")

        #print("Writing %s"%xml_file)
        
        for key in xml_data.keys():
            if key in ['GlobalJobId', 'TaskType', 'Owner', 'CRAB_ReqName', 'CRAB_JobSW', 'CRAB_AsyncDest', 'MATCH_EXP_JOB_GLIDEIN_Entry_Name', 'MATCH_EXP_JOB_GLIDEIN_CMSSite']:
                # Put non numeric values also but store them on the description field 
                numericval = SubElement(data, "numericvalue")
                numericval.set("name",key)
                numericval.set("desc",str(xml_data[key]))
                numericval.text = '1'
            else:
                numericval = SubElement(data, "numericvalue")
                numericval.set("name",key)
                numericval.text = str(xml_data[key])

        # Preparing xml and saving to file
        try:
           with open(xml_file, 'w') as f:
             f.write(tostring(root))
        except Exception, e:
           pprint(str(e))
        
        return xml_file
    

    def publishXML(self,xmlFile):
        # push the XML to elasticSearch 
        return 1 # just to disable publication on ES since it will not work from outside of CERN
        try:
            cmd = "curl -i -F file=@" + xmlFile + " xsls.cern.ch"
            pu = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except:
            print "Failed to publish %s on ES."%xmlFile
            return 1
        return 0

    def deleteFile(self, fileToDelete):
        try:
            os.remove(fileToDelete)
        except:
            print "Failed to delete %s"%fileToDelete
            pass
                   
    def parseHistoryFile(self, historyFile):
        xml_out = {}
        with open(historyFile) as fd:
            job_ad = classad.parseOld(fd)
            for key in job_ad.keys():
                temp = ''
                try:
                    temp = str(int(job_ad[key])) # force boolean values to be converted to integer
                except:
                    temp = job_ad[key]
                    if key not in ['GlobalJobId', 'TaskType', 'Owner', 'CRAB_ReqName', 'CRAB_JobSW', 'CRAB_AsyncDest', 'MATCH_EXP_JOB_GLIDEIN_Entry_Name', 'MATCH_EXP_JOB_GLIDEIN_CMSSite']:
                        continue
                xml_out[key] = temp

        if len(xml_out) > 0:
            self.xmlBuffer = xml_out
            self.totalParsed += 1
            return 1

        return 0
        
    def runCondorConfigVal(self, variableToCatch):
        condor_config_val = 'condor_config_val ' + variableToCatch
        varToRet = str(subprocess.Popen(condor_config_val, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.read())
        varToRet = varToRet.strip()
        if 'Not defined' in varToRet:
            varToRet = ''
        return varToRet

    def execute(self):   
        ret = self.getFilesToParse()
        xmlToDelete = []
        if ret == 0:
            print("No files to parse on %s. Exiting.."%self.PER_JOB_HISTORY_DIR)
            return
                  
        print("Going to parse %i files"%ret)
        
        
        # generate all XML files
        for theFile in  self.filesToParse:
            fileToCheck = os.path.join(self.PER_JOB_HISTORY_DIR, theFile)
            if self.parseHistoryFile(fileToCheck) == 1:
                xmlToDelete.append(self.writeXMLToFile(self.xmlBuffer))

        print("Parsed %i files"%self.totalParsed)        
        print("Going to feed ES")
        for xmlFile in xmlToDelete:
            if self.publishXML(xmlFile) == 0:
                self.deleteFile(xmlFile)
            
        # delete history files
        for fileToDelete in self.filesToParse:
            self.deleteFile(os.path.join(self.PER_JOB_HISTORY_DIR, fileToDelete))

if __name__ == '__main__':
    feeder1 = jobHistoryFeed('PER_JOB_HISTORY_DIR')
    if feeder1.isRunable():
        feeder1.execute()
    else:
        # failed to run over the primary/uniq schedd 
        exit()
        
    feeder2 = jobHistoryFeed('SCHEDD.SECOND.PER_JOB_HISTORY_DIR')
    if feeder2.isRunable():
        feeder2.execute()
