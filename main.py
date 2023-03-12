from bs4 import BeautifulSoup
import requests
import sys, os
from datetime import datetime, time
import time
import calendar
import hashlib
import email, smtplib, ssl
import cfg_parser
import re

__author__ = "danny.ruttle@gmail.com"
__version__ = "3.4"
__date__ = "12-03-2023"

"""
Credit to:  https://www.pluralsight.com/guides/web-scraping-with-beautiful-soup

What this code does...

It queries the Florida launch timetable page (https://floridareview.co.uk/things-to-do/current-launch-schedule) and returns 
the results in an easy to read summary as a table in an HTML page.

It then runs periodically using crond and uses md5 to determine whether the page has been updated and emails the output to a list of recipients
define in the config file.


Features Complete (beyond version 2.10a)
-----------------
1. Added class for local dataAccess (to files on disk) - DataAccessLocal.py
2. Fixed bug with some launches not appearing when day og month was blank - now set to last day in month to meet date comparison algorithm rules
3. missions_array now sorted in date order - bug fixed with last actual last day (or default date applied to end of month or quarter) not sorting correctly 
4. check_page_update() now reads the missions_array rather than the tags coming back from the page to detect changes.
5. self.notify_update() now within the if (check_page_update()) structure
6. check_page_update() now reads the missions_array into current_missions (based on today's date) prior to the call to check_has_updated()

TO DO
-----
1. update the page with the most recent mission that was scheduled/launched and include all details.
2. Maybe update to local UK time?  Needs a lot of effort to pull this out
3. Add EC2 container to host a static web page for testing...





MUCH LATER
----------
1. Plug password crypto back in (_rust import issue on AWS with this so app pwd now in the code)

"""


def process():
    l = Launch()
    l.process()


class Launch(object):

    def __init__(self):
        self.dataAccess = None
        self.config_dict = {}

    def process(self):
        """
        :param :
        :return:
        """

        self.config_dict = self.read_config("config.txt")
        self.env = self.config_dict.get("environment")

        if self.env == "cloud":
            import DataAccessCloud
            self.dataAccess = DataAccessCloud.dataAccess()
        else:
            import DataAccessLocal
            self.dataAccess = DataAccessLocal.dataAccess()

        # override bot protection on floridareview site
        headers = {'User-Agent': 'SpaceSchedule'}
        content = requests.get("https://floridareview.co.uk:443/things-to-do/current-launch-schedule", headers=headers)

        soup = BeautifulSoup(content.text, 'html.parser')

        tags = soup.find_all(['h2', 'p'])  # Extract and return first occurrence of h2
        #(tags)

        # need to build an array of arrays here, e.g. [[date],mission_details,launch pad, link] link -> #march72023-spacexfalcon9intelsat40e
        missions_array = []
        ctrl_flag = False  # controls when the process stops appending to the mission array (this_mission)
        this_mission = []
        for tag in tags:
            if not ctrl_flag:
                this_mission = []
            if str(tag)[0:6] == "<h2 id":  # this is a heading we are interested in
                mission = self.process_h2(tag)
                if mission:
                    this_mission = mission
                    ctrl_flag = True

            if ctrl_flag:
                if tag.get_text()[0:6] == "Launch":
                    this_mission.append(tag.get_text())
                    missions_array.append(this_mission)
                    ctrl_flag = False

        # only interested in missions from midnight of the start of today onwards...
        current_day = (int(time.time() // 86400)) * 86400  # output = 6614352000
        current_missions = []
        for mission in missions_array:
            mission_date = datetime(int(mission[0][0]), int(mission[0][1]), int(mission[0][2]), 0, 0)
            mission_date = calendar.timegm(mission_date.timetuple())
            if mission_date >= current_day:
                current_missions.append(mission)

        if self.check_has_updated(current_missions):  # see if digest of tags array is different
            # sort the missions by date
            missions_array_sorted = sorted(current_missions, key=lambda x: self.sortDate(x))
            output_string = self.generate_output(missions_array_sorted)

            self.notify_update(output_string)

    def sortDate(self, mission):
        """
        :param mission: list of strings [year, month, date]
        :return: unix epoch as timestamp
        """
        date_list = mission[0]
        date_epoch = datetime(int(date_list[0]), int(date_list[1]), int(date_list[2]),0,0)
        my_date = calendar.timegm(date_epoch.timetuple())

        """ now adjust timestamp based on the second value in the mission array! aaargh!!
        
        [['2023', '06', '30'], 'June 30 2023',...]
        [['2023', '06', '30'], 'June 2023',...]
        if string.split mission[1] == 2, reduce epoch time by 2 days :-)
        
        """
        if len(str.split(mission[1], " ")) == 2:
            my_date = my_date - 172800
        return my_date

    def read_config(self, config):
        """
        Read from config file into a dictionary
        :param config: text file with
        :return: dictionary containing config properties
        """
        cp = cfg_parser.config_parser()
        return cp.read(config)

    def check_has_updated(self, tags):
        """
        Generate a signature for incoming data and compare with the last version
        :param tags: multidemensional array of data returned from the web page
        :return: Boolean
        """

        sig = hashlib.shake_128()
        sig.update(str.encode(str(tags)))
        sig = sig.hexdigest(32)

        sys.stderr.write("new signature = %s\n" % str(sig))

        # call DataAccess class depending on the value in config_dict
        if self.env == "cloud":
            table = self.config_dict.get("digest_table")
            Digest = self.dataAccess.getDigest(table)
        else:
            Digest = self.dataAccess.getDigest("signature.txt")

        sys.stderr.write("old signature = %s\n" % str(Digest))

        if self.config_dict.get("sig_check") == "0":  # for testing - saves time editing the Sig in DynamoDB
            old_sig = "test"
        else:
            old_sig = Digest

        # now compare
        if sig == old_sig:
            # do nothing
            self.log_run(sig, "did not update")
            return False
        else:
            # ### call DataAccesCloud and replace the sig ###
            self.dataAccess.replaceDigest(sig) # same method signature for both classes :-)
            self.log_run(sig, "updated")
            return True

    def process_h2(self, tag):
        """
        Get date in a form where it can be compared with sysdate
        also return mission detail in an array
        tag.text = 'January 3, 2023 - SpaceX Falcon 9, Transporter 6' (an example)
                    or March 2023 - SpaceX Falcon 9, Polaris Dawn' (an example)
        :param tag:
        :return: array [[<date>], <mission>, <taganchor>, <Launch Pad>]
        """
        month_dict = {  # used to pad leading zero and assign last day of month for launches with a day defined
            "January": ["01", "31"],
            "February": ["02", "28"],
            "March": ["03","31"],
            "April": ["04","30"],
            "May": ["05","31"],
            "June": ["06","30"],
            "July": ["07","31"],
            "August": ["08","31"],
            "September": ["09","30"],
            "October": ["10","31"],
            "November": ["11","30"],
            "December": ["12","31"]
        }

        details = tag.get_text()
        # Need to make sure we are dealing with a date
        if details[0:3] in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'NET',
                            'Qua']:
            # print(details)

            """
            January 3, 2023 - SpaceX Falcon 9, Transporter 6
            March 2023 - SpaceX Falcon 9, Polaris Dawn
            ['March 2023', 'SpaceX Falcon 9, Polaris Dawn']
            ['March 2023']

            bug #001 fix to this section.  Needed to remove processing of commas from date portion of the h2 tag as these are not uniformally structured 

            # 'January 3, 2023 - SpaceX Falcon 9, Transporter 6'
            # or 'March 2023 - SpaceX Falcon 9, Polaris Dawn'
            # or 'February, 2023 - Relativity Space Terran 1, Good Luck, Have Fun'
            # or 'NET March 2, 2023 - SpaceX Falcon 9, USCV-6 (NASA Crew Flight 6)'
            """

            # first deal with the NET entries!
            if str.lower(details[
                         0:3]) == 'net':  # need to remove the the start from "NET March 2, 2023 - SpaceX Falcon 9, USCV-6 (NASA Crew Flight 6)"
                details = details[4:]  # need to get the space too, so it trims the start and leaves the date in place

            # next deal with those dates that are allocate to a quarter
            if str.lower(details[0:3]) == 'qua':  # "Quarter 2, 2023 - SpaceX Falcon 9, Galaxy 37"
                quarter_dict = {"2": "June 30",
                                "3": "September 30",
                                "4": "December 31"}
                details = "%s%s ***allocated to Quarter %s***" % (quarter_dict.get(details[8]), details[9:], details[8])

            mission_split = details.split("-", 1)
            mission_date = mission_split[0].replace(',', '')
            mission_string = mission_split[1].strip()

            human_date = mission_date.strip()

            date_array = human_date.split(' ')
            # do a length check here...
            if len(date_array) == 3:  # 'January 3 2023'
                # ['January','3',' 2023 ']
                year = date_array[2]
                # returns '2023'
                day = date_array[1]
                # returns ['January',' 3']
                month = month_dict.get(date_array[0])[0]
            else:  # 'January 2023'
                # ['January','2023']
                year = date_array[1]
                # returns '2023'
                month = month_dict.get(date_array[0])[0]
                # need to assign a default day value to last day of month!
                day = month_dict.get(date_array[0])[1]

            # get tag id so we can use the anchor in the details link
            anchor = tag.get('id')
            return [[year, month, day], human_date, mission_string, anchor]
        else:
            pass

    def generate_output(self, missions_array):
        """
        Generates html, filtered by sys date (should mak the sysdate part configurable?)
        :return:

        reference:  https://docs.python.org/3/library/time.html
        """
        # print(missions_array)
        date_string = f'{datetime.now():%Y-%m-%d %H:%M:%S%z}'
        html_head = """<!DOCTYPE html><html><head>
        <meta charset="utf-8" />
        <style type = text/css>
        .styled-table {
        border: collapse;
        margin: 25px 0;
        font-size: 0.8em;
        font-family: sans-serif;
        min-width: 400px;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
        }
    	.styled-table th, 
    	.styled-table td { 
    	border: collapse;
    	vertical-align: top;
    	}

    	.styled-table tr.d0 td {
    	  background-color: #e6f1fc;
    	}
    	.styled-table tr.d1 td {
    	  background-color: #EEEEEE;
    	}
        h1 {
        font-size: 1.5em;
        font-family: sans-serif;
        }
        body {
        font-size: 0.8em;
        font-family: sans-serif;
        }
        </style>
        <title>Space Launch Summary</title></head>
                        <body>
                        <h1>Space Launch Summary</h1>
                        <p>Generated from 
                        <a href= "https://floridareview.co.uk/things-to-do/current-launch-schedule">https://floridareview.co.uk/things-to-do/current-launch-schedule</a> on %s
                        <p>%s""" % (date_string, self.config_dict.get("broadcast", ""))

        html_footer = """<p><b>You can also check Florida launch schedules <a href=https://www.spacelaunchschedule.com/category/fl/>here</a></b>
        <p>Watch LIVE launches on <a href=https://www.youtube.com/live/MWelnI4zJpU>Space flight Now</a> or <a href=https://www.youtube.com/watch?v=CunF9QllJzU>The Launch Pad</a>.
		<p>Also on <a href=https://www.youtube.com/watch?v=21X5lGlDOfg>NASA Live TV</a> too, but there's lots of other stuff on this channel that seems to get in the way!</body>
                    </html>"""

        table_head = """
        <table class = "styled-table"><thead><tr align=left>
                <th nowrap>Date</th>
                <th>Mission</th>
                <th>Launch Pad</th>
            </tr>
        </thead>
        <tbody>\n"""

        table_footer = """</tbody>
            </table>"""

        """
        [[['2022', '12', '31'], 'SpaceX Falcon 9, Transporter 6', 'january32023-spacexfalcon9transporter6', 'Launch was from launch pad SLC-40 with a launch time of 9:56 a.m. EST.'],...
        """
        table_detail_string = ""
        style_count = 0  # used for alternate style on table rows
        for mission in missions_array:
            style_count += 1
            # first assign any null days (no date defined in schedule) to 1st of month for comparison only
            mission_day = mission[0][2]
            # print(mission_day)
            mission_date = datetime(int(mission[0][0]), int(mission[0][1]), int(mission_day), 0, 0)
            mission_date = calendar.timegm(mission_date.timetuple())
            # print("mission_date = %s, current_time = %s" % (mission_date, current_time))
            mission_row_string = self.create_mission_row(mission, style_count)
            table_detail_string += mission_row_string
        return html_head + table_head + table_detail_string + table_footer + html_footer

    def create_mission_row(self, mission, style_count):
        """
        Generate table row from:
        [['2023', '01', '31'],
                'January 31, 2023',
                'SpaceX Falcon 9, Starlink 5–3',
                'january312023-spacexfalcon9starlink5-3',
                'Launch is from launch pad LC-39A with a launch time of 3:27 a.m. EST.']
        :param mission:
        :return:
        """
        base_site_url = "https://floridareview.co.uk/things-to-do/current-launch-schedule"

        # set style for this row
        if style_count % 2 == 0:
            row_string = "<tr class=d0>"
        else:
            row_string = "<tr class=d1>"
        # human date
        """
        see if there's a time in mission[4]
        """
        t_string = "...."
        t = re.search(r'\s(\d{1,2}\:\d{2}\s?(?:A\.M\.|P\.M\.|a\.m\.|p\.m\.))', mission[4])
        if t:
            t_string = t[0]
            row_string += "<td nowrap>%s &#64; %s</td>" % (mission[1], t_string)
        else:
            row_string += "<td nowrap>%s</td>" % mission[1]
        # mission details
        row_string += "<td><a href = %s#%s>%s</a></td>" % (base_site_url, mission[3], mission[2])
        # launch details
        # example Launch is from launch pad SLC-40 with a launch time of 1.12PM EST.
        # 1 split on "with"
        # 2 regex search on launchpad * and return
        match_exp = r'\s((?:launch pad|launchpad).*)'
        lp_split = str.split(mission[4], " with ")
        lp_length = len(lp_split)
        if lp_length > 1:  # has time portion on end
            launchpad = re.search(match_exp, lp_split[0])[0]
        else:  # no time portion
            launchpad = re.search(match_exp, mission[4])[0]
        launchpad = str.replace(launchpad, "launchpad ", "")
        launchpad = str.replace(launchpad, "launch pad ", "")
        launchpad = str.replace(launchpad, ".", "")

        row_string += "<td>%s</td>" % launchpad

        row_string += "</tr>\n"
        return row_string

    def notify_update(self, output):
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # encrypted credentials for sending output via gmail
        recipients = self.config_dict.get("recipients")
        # gpwd = 'mpdndvqvvrgrwwcs'
        # encrypted credentials for sending output via gmail

        gpwd = 'mpdndvqvvrgrwwcs'

        subject = self.config_dict.get("email_notification_subject")
        text = "An update has been made to the page - exciting!"
        sender_email = "rockets.spotter@gmail.com"
        receiver_email = str.split(recipients, ",")
        password = gpwd  # this is a google app password - uses pycrypto for this - see manual amend!

        # Create a multipart message and set headers
        message = MIMEMultipart("alternative")
        message["From"] = sender_email
        message["To"] = recipients
        message["Subject"] = subject
        message["Bcc"] = "rockets.spotter@gmail.com"  # Recommended for mass emails

        html = output[15:]  # removes doctype declaration

        # Turn these into plain/html MIMEText objects
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        message.attach(part1)
        message.attach(part2)

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())

    def log_run(self, sig, action):

        date_string = f'{datetime.now():%Y-%m-%d %H:%M:%S%z}'
        output = "Script ran at %s and %s the output, digest was %s" % (date_string, action, sig[-4:])

        log_table = self.config_dict.get("log_table")
        sys.stderr.write("%s" % log_table)
        if self.env == "cloud":
            result = self.dataAccess.logRun(log_table, date_string, output, sig)
            sys.stderr.write("log response = %s" % result)
        else:
            self.dataAccess.logRun(output)
        # now email the log to rockets.spotter@gmail.com
        self.notify_log(output)

    def notify_log(self, output):
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # encrypted credentials for sending output via gmail
        # pwd = config_dict.get("pwd")
        # key = config_dict.get("key")

        gpwd = 'mpdndvqvvrgrwwcs'

        # ***********************************  need to look at email mime method, etc... ****************
        subject = self.config_dict.get("email_log_subject")
        text = output
        sender_email = "rockets.spotter@gmail.com"
        receiver_email = "rockets.spotter@gmail.com"
        password = gpwd  # this is a google app password - uses pycrypto for this - see manual amend!

        # Create a multipart message and set headers
        message = MIMEMultipart("alternative")
        message["From"] = sender_email
        message["To"] = "rockets.spotter@gmail.com"
        message["Subject"] = subject
        message["Bcc"] = "rockets.spotter@gmail.com"  # Recommended for mass emails

        html = output[15:]  # removes doctype declaration

        # Turn these into plain/html MIMEText objects
        part1 = MIMEText(text, "plain")

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        message.attach(part1)

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())


if __name__ == "__main__":
    process()
