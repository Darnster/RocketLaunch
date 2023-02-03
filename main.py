
from bs4 import BeautifulSoup
import requests
import sys
from datetime import datetime
import time
import calendar
import hashlib
import email, smtplib, ssl
import CryptProcess # for gmail password encryption
import cfg_parser

__author__ = "danny.ruttle@gmail.com"
__version__ = "0.7"
__date__ = "03-02-2023"

"""
Credit to:  https://www.pluralsight.com/guides/web-scraping-with-beautiful-soup

What this code does...

It queries the Florida launch timetable page (https://floridareview.co.uk/things-to-do/current-launch-schedule) and returns 
the results in an easy to read summary as a table in an HTML page.

It then runs periodically using crond and uses md5 to determine whether the page has been updated and emails the output.
.... may publish to a location on my phone instead???

Features Complete
-----------------
1. normalise dates to compare with sysdate DONE
2. html + css for output
3. hash the response to see if it has changed before generating the output (hash stored in (signature.txt))
4. logging of the result of each run of the script
5. email output to me when something changes - possibly configurable
6. encrypt app password for gmail
7. HTML now published to body of email

Bugs fixed:
#001 Source page added a descriptive date with a comma 


TO DO
-----
1. Schedule it somewhere (on my phone)
"""


def process():
    """
    :param :
    :return:
    """

    config_dict = read_config("config.txt")
    pwd = config_dict.get("pwd")
    key = config_dict.get("key")

    content = requests.get("https://floridareview.co.uk/things-to-do/current-launch-schedule")
    # print(content)
    soup = BeautifulSoup(content.text, 'html.parser')
    tags = soup.find_all(['h2', 'p'])  # Extract and return first occurrence of h2
    #  print(tags)  # Print row with HTML formatting
    if check_page_update(tags):  # see if digest of tags array is different
        # need to build an array of arrays here, e.g. [[date],mission_details,launch pad, link] link -> #march72023-spacexfalcon9intelsat40e
        missions_array = []
        ctrl_flag = False #controls when the process stops appending to the mission array (this_mission)
        this_mission = []
        for tag in tags:
            if ctrl_flag == False:
                this_mission = []
            if str(tag)[0:6] == "<h2 id":  # this is a heading we are interested in
                mission = process_h2(tag)
                if mission:
                    this_mission = mission
                    #print(this_mission)
                    ctrl_flag = True


            if ctrl_flag == True:
                if tag.get_text()[0:6] == "Launch":
                    this_mission.append(tag.get_text())
                    missions_array.append(this_mission)
                    ctrl_flag = False

        output_string = generate_output(missions_array)

        fh = open("space_launch.html", "w")
        fh.write(output_string)
        fh.close()
        notify_update(key, pwd, output_string)


def read_config(config):
    """
    Read from config file into a dictionary
    :param config: text file with
    :return: dictionary containing config properties
    """
    cp = cfg_parser.config_parser()
    return cp.read(config)



def notify_update(key,pwd, output):
    from email import encoders
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gpwd = CryptProcess.decrypt(bytes(pwd, 'utf-8'), key).decode()


    subject = "rocket Schedule Update"
    text = "An update has been made to the page - exciting!"
    sender_email = "darnster.test@gmail.com"
    receiver_email = "danny.ruttle@gmail.com"
    password = gpwd # this is a google app password - uses pycrypto for this - see manual amend!

    # Create a multipart message and set headers
    message = MIMEMultipart("alternative")
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message["Bcc"] = receiver_email  # Recommended for mass emails


    html = output[15:]

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



def check_page_update(tags):
    """
    Generate a signature for incoming data and compare with the last version
    :param tags: multidemensional array of data returned from the web page
    :return: Boolean
    """
    sig = hashlib.shake_128()
    sig.update(str.encode(str(tags)))
    sig = sig.hexdigest(32)
    # print(sig)
    # now compare
    last_signature = open('signature.txt', "r")
    old_sig = last_signature.readline()
    last_signature.close()
    # print(old_sig)
    if sig == old_sig:
        # do nothing
        log_run(sig, "did not update")
        return False
    else:
        new_sig = open('signature.txt', "w")
        new_sig.write(sig)
        new_sig.close()
        log_run(sig, "updated")
        return True


def log_run(sig, action):
    logfile = open("run_log.txt", "a")
    date_string = f'{datetime.now():%Y-%m-%d %H:%M:%S%z}'
    logfile.write("Script ran at %s and %s the output, digest was %s\n" % (date_string, action, sig))




def generate_output(missions_array):
    """
    Generates html, filtered by sys date (should mak the sysdate part configurable?)
    :return:

    reference:  https://docs.python.org/3/library/time.html
    """
    #print(missions_array)
    date_string = f'{datetime.now():%Y-%m-%d %H:%M:%S%z}'
    html_head = """<!DOCTYPE html><html><head>
    <meta charset="utf-8" />
    <style type = text/css>
    .styled-table {
    border-collapse: collapse;
    margin: 25px 0;
    font-size: 0.9em;
    font-family: sans-serif;
    min-width: 400px;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
    }
    h1 {
    font-size: 3em;
    font-family: sans-serif;
    }
    body {
    font-size: 0.9em;
    font-family: sans-serif;
    }
    </style>
    <title>Space Launch Summary</title></head>
                    <body>
                    <h1>Space Launch Summary</h1>
                    <p>Generated from 
                    <a href= "https://floridareview.co.uk/things-to-do/current-launch-schedule">https://floridareview.co.uk/things-to-do/current-launch-schedule</a> on %s""" % date_string

    html_footer = """</body>
                    </html>"""

    table_head = """
    <table class = "styled-table"><thead><tr>
			<th nowrap>Date</th>
			<th>Mission</th>
			<th>Launch Pad</th>
			<th>More Information</th>
		</tr>
	</thead>
	<tbody>\n"""

    table_footer = """</tbody>
        </table>"""

    """
    [[['2022', '12', '31'], 'SpaceX Falcon 9, Transporter 6', 'january32023-spacexfalcon9transporter6', 'Launch was from launch pad SLC-40 with a launch time of 9:56 a.m. EST.'],...
    """
    table_detail_string = ""
    current_time = time.time() # output = 1674993381.0381138
    for mission in missions_array:
        # print(mission)
        #first assign any null days (no date defined in schedyule) to 1st of month for comparison only
        if mission[0][2] == "null":
            mission_day = 1
        else:
            mission_day = mission[0][2]
        # print(mission_day)
        mission_date = datetime(int(mission[0][0]),int(mission[0][1]),int(mission_day),0,0)
        mission_date = calendar.timegm(mission_date.timetuple())
        if mission_date >= current_time:
            #print("mission_date = %s, current_time = %s" % (mission_date, current_time))
            mission_row_string = create_mission_row(mission)
            table_detail_string += mission_row_string
    return html_head + table_head + table_detail_string + table_footer + html_footer




def create_mission_row(mission):
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
    row_string = "<tr>"
    # human date
    row_string += "<td>%s</td>" % mission[1]
    # mission details
    row_string += "<td>%s</td>" % mission[2]
    # launch details
    row_string += "<td>%s</td>" % mission[4]
    # link
    row_string += "<td><a href = %s#%s>Details</a></td>" % (base_site_url, mission[3])
    row_string += "</tr>\n"
    return row_string





def process_h2(tag):
    """
    Get date in a form where it can be compared with sysdate
    also return mission detail in an array
    tag.text = 'January 3, 2023 - SpaceX Falcon 9, Transporter 6' (an example)
                or March 2023 - SpaceX Falcon 9, Polaris Dawn' (an example)
    :param tag:
    :return: array [[<date>], <mission>, <taganchor>, <Launch Pad>]
    """
    month_dict = {# used to pad leading zero
        "January" : "01",
        "February" : "02",
        "March" : "03",
        "April" : "04",
        "May" : "05",
        "June" : "06",
        "July" : "07",
        "August" : "08",
        "September" : "09",
        "October" : "10",
        "November" : "11",
        "December" : "12"
    }

    details = tag.get_text()
    # Need to make sure we are dealing with a date
    if details[0:3] in ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']:
        #print(details)

        """
        January 3, 2023 - SpaceX Falcon 9, Transporter 6
        March 2023 - SpaceX Falcon 9, Polaris Dawn
        ['March 2023', 'SpaceX Falcon 9, Polaris Dawn']
        ['March 2023']
        
        bug #001 fix to this section.  Needed to remove processing of commas from date portion of the h2 tag as these are not uniformally structured 
        
        # 'January 3, 2023 - SpaceX Falcon 9, Transporter 6'
        # or 'March 2023 - SpaceX Falcon 9, Polaris Dawn'
        # or 'February, 2023 - Relativity Space Terran 1, Good Luck, Have Fun'
        """
        mission_split = details.split("-")
        mission_date = mission_split[0].replace(',', '')
        mission_string = mission_split[1].strip()
        print(mission_date)
        human_date = mission_date.strip()
        print(human_date)
        date_array = human_date.split(' ')
        print(date_array)
        # do a length check here...
        if len(date_array) == 3:  # 'January 3 2023'
            # ['January','3',' 2023 ']
            year = date_array[2]
            # returns '2023'
            day = date_array[1]
            # returns ['January',' 3']
            month = month_dict.get(date_array[0])


        else: # 'January 2023'
            # ['January','2023']
            year = date_array[1]
            # returns '2023'
            month = month_dict.get(date_array[0])
            day = "null"

        # get tag id so we can use the anchor in the details link
        anchor = tag.get('id')
        return [[year, month, day], human_date, mission_string, anchor]
    else:
        pass



if __name__ == "__main__":
    process()
