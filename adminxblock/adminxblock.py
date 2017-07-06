# This project is Open edX server task automator using XBlock.
# The objective of the project is to create an XBlock which will perform
# all the tasks which a system adminstrator frequently performs in the
# lifecycle of the Open edX server.

import pkg_resources

from xblock.core import XBlock
from xblock.fields import Scope, String
from xblock.fragment import Fragment
import logging

log = logging.getLogger(__name__)


class AdminXBlock(XBlock):

    # This is the variable which carries the final result to be displayed from the python code to javascript code
    success = String(
        default='', scope=Scope.user_state,
        help="Result variable",
    )

    userid = String(
        default='', scope=Scope.user_state,
        help="User ID",
    )

    # Handy helper for getting resources from our kit.
    def resource_string(self, path):
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    # The primary view which is shown to the students while opening the student view of the xblock.
    # We are now trying to link all the files needed to be displayed as student view, linking the html,css,js files.
    # As this project is to be only viewed and accessed by admins and nothing for students or staff.
    # In the beginning, we are trying to get ID of the user who is logged in
    # and check if he is a superuser or not
    # if he is a superuser, he is allowed to access the XBlock.
    # else he is not allowed to access the XBlock
    def student_view(self, context=None):
        self.userid = self.xmodule_runtime.user_id
        import MySQLdb
        db = MySQLdb.connect("localhost", "root", "", "edxapp")
        cursor = db.cursor()
        sql = "select is_superuser from auth_user where id="+str(self.userid)
        cursor.execute(sql)
        results = cursor.fetchall()
        temp = 0
        l=[]
        for row in results:
            l.append(row[0])
        if l[0]==1:
            html = self.resource_string("static/html/adminxblock.html")
            frag = Fragment(html.format(self=self))
            frag.add_css(self.resource_string("static/css/adminxblock.css"))
            frag.add_javascript(self.resource_string("static/js/src/adminxblock.js"))
            frag.initialize_js('StudioView')
            return frag    
        else:
            html = self.resource_string("static/html/studioview.html")
            frag = Fragment(html.format(self=self))
            frag.add_css(self.resource_string("static/css/studioview.css"))
            frag.add_javascript(self.resource_string("static/js/src/studioview.js"))
            frag.initialize_js('AdminXBlock')
            return frag

    # The secondary view which is shown to the admin while opening the studio view of the xblock.
    # We are now trying to link all the files needed to be displayed as studio view, linking the html,css,js files.
    # As this project is to be only viewed and accessed by admins, entire functionality and everything is to be available in this itself.
    def studio_view(self, context=None):
        html = self.resource_string("static/html/studioview.html")
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/studioview.css"))
        frag.add_javascript(self.resource_string("static/js/src/studioview.js"))
        frag.initialize_js('AdminXBlock')
        return frag        


    # Refer to the documentation at
    # https://goo.gl/D6MyJ5
    # for more details of server administration

    # This is the main handler where all the functionality of xblock will be performed.
    # The functionalities to be performed will be explained below in detail
    @XBlock.json_handler
    def perform(self, data, suffix=''):
        # The modules needed for the working of this xblock
        import os
        import time
        import MySQLdb
        import shutil
        from subprocess import Popen, PIPE
        from xml.dom import minidom
        # data['detail'] is the data which we are sending from js file received from the user, embedding it inside of ajax request
        # next we are trying to split it. to be used in program.
        # basically we receive it in the form of option_selected+parameters_for_that_option.
        # its got stored in the list variable
        list = data['detail'].split()
        # this is the variable in which we will be concatenating whatever result we get and we will finally send to be displayed in result html page
        res = ''


        # Delete operation. Objective is to delete a particular course on the server.
        # we move to a particular directory on server '/edx/app/edxapp/edx-platform' to execute the code in xblock. Using os module in python.
        # then we use the command. executing it in shell using popen.
        # and we are pre-embedding the yes-yes using the popen, from the subprocess module.
        # after that, just to verify if the course is actually deleted or not, we check it from
        # the 'course_overviews_courseoverview' table, available in edxapp, (mysql database)
        # if the course is available in the table, operation was unsuccessful and we print it unsucessful
        # else if course is not available in the table, operation was sucessful and we print it successful.
        if list[0] == 'd01':
            sql_user = 'root'
            database = 'edxapp'
            db_mysql = MySQLdb.connect(user=sql_user, db=database)
            query = "select id from course_overviews_courseoverview where id='"+list[1]+"'";
            mysql_cursor = db_mysql.cursor()
            mysql_cursor.execute(query)
            courses1 = mysql_cursor.fetchall()
            l1 = []
            for b1 in courses1:
                for c1 in b1:
                    l1.append(c1)
            if len(l1)==1:
                os.chdir('/edx/app/edxapp/edx-platform')
                command = '/edx/bin/python.edxapp ./manage.py cms --settings=aws delete_course ' + list[1]
                p = Popen(command, shell=True, stdin=PIPE)
                p.stdin.write("y\n")
                p.stdin.write("y\n")
                p.wait()
                query = "select id from course_overviews_courseoverview where id='"+list[1]+"'";
                db_mysql = MySQLdb.connect(user=sql_user, db=database)
                mysql_cursor = db_mysql.cursor()
                mysql_cursor.execute(query)
                courses = mysql_cursor.fetchall()
                l = []
                for b in courses:
                    for c in b:
                        l.append(c)
                if len(l)==1:
                    res += 'Deletion of the course "' + list[1] + '" including all dependancies of the course, its associated data and associated users has failed'
                else:
                    res += 'Deletion of the course "' + list[1] + '" including all dependancies of the course, its associated data and associated users is successful'
            else:
                res += 'Course not available'


        # Import a course from git repository and create a new course out of it on server, on the go.
        # in front end, user must have entered only git url. an example of git url is https://github.com/edx/edx-demo-course.git
        # at the time of import, the folder will be created,in temp folder same as last part of url.
        # we need to extract that particular part of url. here it is edx-demo-course.
        # now this folder we move it to the location where we plan to install it.
        # -------------------------------------------------------------------------------
        # besides that, we also extract the name of course, available in the xml file 'course.xml'
        # located in the driectory we imported from git.
        # now, after installing the code at particular location, we check if the particular course name is located
        # in the 'course_overviews_courseoverview' table, available in edxapp, (mysql database)
        # if the course is available in the table, operation was sucessful and we print it successful.
        # else if course is not available in the table, operation was unsuccessful and we print it unsucessful.
        elif list[0] == 'd02':
            os.chdir('/var/tmp')
            course = list[1].split('/')[-1].split('.')[0]
            log.info('course name is found as '+course)
            shutil.rmtree(course, ignore_errors=True)
            comm = 'git clone '+list[1]
            log.info('now git cloning using --- '+comm)
            p = Popen(comm.encode('utf-8'), shell=True, stdin=PIPE)
            p.wait()
            log.info('cloning is over')
            location = course+'/course.xml'
            xmldoc = minidom.parse(location.encode('utf-8'))
            itemlist = xmldoc.getElementsByTagName('course')
            org = itemlist[0].attributes['org'].value
            course1 = itemlist[0].attributes['course'].value
            url_name = itemlist[0].attributes['url_name'].value
            course_url = org + '+' + course1 + '+' + url_name
            log.info(course_url)
            os.chdir('/edx/app/edxapp/edx-platform')
            log.info('dir changed and starting to execute')
            command = '/edx/bin/python.edxapp ./manage.py cms --settings=aws import /edx/var/edxapp/data  /var/tmp/' + course
            p1 = Popen(command, shell=True, stdin=PIPE)
            p1.wait()
            sql_user = 'root'
            database = 'edxapp'
            db_mysql = MySQLdb.connect(user=sql_user, db=database)
            query = "select id from course_overviews_courseoverview"
            mysql_cursor = db_mysql.cursor()
            mysql_cursor.execute(query)
            courses = mysql_cursor.fetchall()
            l = []
            for b in courses:
                for c in b:
                    l.append(c)
            flag = False
            for elem in l:
                if elem.endswith(course_url):
                    flag = True
                    break
            if flag==True:
                res += 'Import course contents(by creating a new course at the time of import) of course "' + course + '" from git repository is successful'
            else:
                res += 'Import course contents(by creating a new course at the time of import) of course "' + course + '" from git repository has failed'


        # Running the asset collections command.
        # its directly implemented as it is from documentation using the python modules.
        # please check modules for more details
        elif list[0] == 'd03':
            # os.chdir('..')
            # os.popen('. /edx/app/edxapp/edxapp_env').read()
            # os.chdir('/edx/app/edxapp/edx-platform')
            # command1 = 'paver update_assets cms --settings=aws'
            # command2 = 'paver update_assets lms --settings=aws'
            # p1 = Popen(command1, shell=True, stdin=PIPE)
            # p1.wait()
            # p2 = Popen(command2, shell=True, stdin=PIPE)
            # p2.wait()
            # res += 'Running of the asset collection commands is successful'
            res += 'Functionality development still in progress'


        # Here the objective being to export our course contents to git repository
        # Functionality is yet to be implemented
        elif list[0] == 'd04':
            res += 'Functionality development still in progress'


        # Here the objective is to activate the user.
        # we need to modify the is_active variable in auth_user table of edxapp mysql database.
        # as soon as we change its value to 1, user gets activated.
        # for sake of verification, we also verify if is_active variable has changed for that particular row.
        # and according send feedback to user regarding the success or failure of query.
        elif list[0] == 'd05':
            email = list[1]
            db = MySQLdb.connect("localhost", "root", "", "edxapp")
            cursor = db.cursor()
            sql = "select is_active from auth_user where email='" + email + "'"
            cursor.execute(sql)
            results = cursor.fetchall()
            temp = 0
            l=[]
            for row in results:
                l.append(row[0])
            if len(l) == 1:
                sql = "update auth_user set is_active = 1 WHERE email = '" + email + "'"
                cursor.execute(sql)
                db.commit()
                sql = "select is_active from auth_user where email='" + email + "'"
                cursor.execute(sql)
                results = cursor.fetchall()
                temp = 0
                for row in results:
                    temp = int(row[0])
                if (temp == 1):
                    res += 'Activation of the user was successful'
                else:
                    res += 'Activation of the user was not successful'
            else:
                res += 'User is not available to be activated'


        # Here the objective is to deactivate the user.
        # we need to modify the is_active variable in auth_user table of edxapp mysql database.
        # as soon as we change its value to 0, user gets deactivated.
        # for sake of verification, we also verify if is_active variable has changed for that particular row.
        # and according send feedback to user regarding the success or failure of query.
        elif list[0] == 'd06':
            email = list[1]
            db = MySQLdb.connect("localhost", "root", "", "edxapp")
            cursor = db.cursor()
            sql = "select is_active from auth_user where email='" + email + "'"
            cursor.execute(sql)
            results = cursor.fetchall()
            temp = 0
            l=[]
            for row in results:
                l.append(row[0])
            if len(l) == 1:
                sql = "update auth_user set is_active = 0 WHERE email = '" + email + "'"
                cursor.execute(sql)
                db.commit()
                sql = "select is_active from auth_user where email='" + email + "'"
                cursor.execute(sql)
                results = cursor.fetchall()
                temp = 1
                for row in results:
                    temp = int(row[0])
                if (temp == 0):
                    res += 'Deactivation of the user was successful'
                else:
                    res += 'Deactivation of the user was not successful'
            else:
                res += 'User is not available to be activated'


        # certificate generation for a particular user in a particular course.
        # we first got to the location '/edx/app/edxapp/edx-platform'
        # now we execute the command for certificate generation
        # for verifying if the certificate is actually generated, we check it from
        # certificates_generatedcertificate tables in edxapp mysql database and if its available,
        # we link it to user_profile table
        # and in the end, attempt to the user's name on the final screen, whose certificate was generated .
        elif list[0] == 'd07':
            os.chdir('/edx/app/edxapp/edx-platform')
            command = "/edx/bin/python.edxapp ./manage.py lms --settings aws regenerate_user -u " + list[1] + " -c " + list[2] + " --insecure"
            p = Popen(command, shell=True, stdin=PIPE)
            p.wait()
            time.sleep(10)
            db5 = MySQLdb.connect("localhost", "root", "", "edxapp")
            cursor = db5.cursor()
            sql = "select c.name from auth_userprofile a,certificates_generatedcertificate c where a.name = c.name and a.mailing_address='"+list[1]+"' and c.status='downloadable'"
            log.info(sql)
	    log.info(type(list[1]))
            cursor.execute(sql)
            results = cursor.fetchall()
            log.info(results)
            names_list = []
            for row in results:
                names_list.append(row[0])
            log.info('AMol Mamol                          '+names_list[0])
            if results:
                res += 'Certificate generation for particular user was successful'
            else:
                res += 'Certificate generation for particular user was unsuccessful'


        # certificate generation for all the users of a particular course.
        # we first got to the location '/edx/app/edxapp/edx-platform'
        # now we execute the command for certificate generation
        # for verifying if the certificates are actually generated, we check it from
        # certificates_generatedcertificate tables in edxapp mysql database
        # and now we will try to print all the names of users, for whom certificate is generated,
        # and for whom certificate is not generated
        # and in the end, print both of these things on the final screen to the user.
        elif list[0] == 'd08':
            db = MySQLdb.connect("localhost", "root", "", "edxapp")
            cursor = db.cursor()
            sql2="select name from certificates_generatedcertificate where course_id = '" + list[1] + "'"
            cursor.execute(sql2)
            results2 = cursor.fetchall()
            names_list2 = []
            for row in results2:
                names_list2.append(row[0])
            if names_list2:
                os.chdir('/edx/app/edxapp/edx-platform')
                command = "/edx/bin/python.edxapp ./manage.py lms --settings aws ungenerated_certs -c " + list[1] + " --insecure"
                p = Popen(command, shell=True, stdin=PIPE)
                p.wait()
                sql = "select name from certificates_generatedcertificate where course_id = '" + list[1] + "' and status = 'downloadable'"
                sql1 = "select name from certificates_generatedcertificate where course_id = '" + list[1] + "' and status != 'downloadable'"
                cursor.execute(sql)
                results = cursor.fetchall()
                cursor.execute(sql1)
                results1 = cursor.fetchall()
                names_list=[]
                names_list1=[]
                for row in results:
                    names_list.append(row[0])
                for row in results1:
                    names_list1.append(row[0])
                if not names_list:
                    res += 'Certificate generation was totally unsuccessful'
                else:
                    res += 'Certificate generation was successful for:<br><ol><li>'+'</li><li>'.join(names_list)+'</li></ol><br><br><br>'
                    if names_list1:
                        res += 'Certificate generation was unsuccessful for:<br><ol><li>'+'</li><li>'.join(names_list1)+'</li></ol>'
            else:
                res+='Course itself is not available'
            

        # No matter which if condition we went through, we surely must be having a result to display to user
        # it may be success or failure
        # that result we store it in the success variable, which is of xblock string datatype
        # and we return this response to the json request we get
        # this marks the end of the perform handler.
        self.success = res
        print self.success
        return {"success": self.success}



# This is to create the scenarios if we would like to see in the workbench while developing your XBlock.
@staticmethod
def workbench_scenarios():
    return [
        ("AdminXBlock",
         """<adminxblock/>
         """),
        ("Multiple AdminXBlock",
         """<vertical_demo>
            <adminxblock/>
            <adminxblock/>
            <adminxblock/>
            </vertical_demo>
         """),
    ]
