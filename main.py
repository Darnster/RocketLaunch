
from bs4 import BeautifulSoup
import requests
import sys
from datetime import datetime
import time
import calendar

"""
Credit to: https://www.pluralsight.com/guides/web-scraping-with-beautiful-soup

What this code does...

It queries the Florida launch timetable page and returns the results in an easy to read summary as a table.
It then emails the results when the page has identified as being updated.

TO DO:
------

1. normalise dates to compare with sysdate DONE
2. hash the response to see if it has changed first?
3. html + css DONE
4. email output to me when something changes - possibly configurable
5. schedule it somewhere (on my phone)
"""


def process():
    content = requests.get("https://floridareview.co.uk/things-to-do/current-launch-schedule")
    # print(content)
    soup = BeautifulSoup(content.text, 'html.parser')
    tags = soup.find_all(['h2', 'p'])  # Extract and return first occurrence of h2
    # print(tags)  # Print row with HTML formatting

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
    print(output_string)
    fh = open("space_launch.html", "w")
    fh.write(output_string)
    fh.close()

def generate_output(missions_array):
    """
    Generates html, filtered by sys date (should mak the sysdate part configurable?)
    :return:

    reference:  https://docs.python.org/3/library/time.html
    """
    #print(missions_array)
    html_head = """<!DOCTYPE html><html><head>
    <style type = text/css>
    .styled-table {
    border-collapse: collapse;
    margin: 25px 0;
    font-size: 0.9em;
    font-family: sans-serif;
    min-width: 400px;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
    }
    </style>
    <title>Space Launch Summary</title></head>
                    <body>
                    <h1>Space Launch Summary</h1>"""

    html_footer = """</body>
                    </html>"""

    table_head = """
    <table class = "styled-table"><thead><tr>
			<th>Date</th>
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
        """
        # 'January 3, 2023 - SpaceX Falcon 9, Transporter 6'
        # or March 2023 - SpaceX Falcon 9, Polaris Dawn
        mission_precision = details.split(",")
        if len(mission_precision) == 3: # pattern is  January 3, 2023 - SpaceX Falcon 9, Transporter 6    ... has 2 commas
            #print("mission precision = 3")
            details_string = details.split(" - ")  # normalise date for sysdate comparison
            # returns ['January 3, 2023 ',' SpaceX Falcon 9, Transporter 6']
            mission_string = details_string[1].strip()
            # returns 'SpaceX Falcon 9, Transporter 6'
            human_date = details_string[0].strip()
            # returns January 3, 2023
            date_string = details_string[0].split(',')
            # returns ['January 3',' 2023 ']
            year = date_string[1].strip()
            # returns '2023'
            month_day = date_string[0].split(' ')
            # returns ['January',' 3']
            month = month_dict.get(month_day[0])
            try:
                day = month_day[1]
            except:
                day = "null"


        else: # March 2023 - SpaceX Falcon 9, Polaris Dawn   ... has only one comma
            #print("mission precision = 2")
            details_string = details.split(" - ")  # normalise date for sysdate comparison
            # returns ['March 2023 ',' SpaceX Falcon 9, Polaris Dawn']
            human_date = details_string[0].strip()
            # returns 'March 2023'
            mission_string = details_string[1].strip()
            # returns 'SpaceX Falcon 9, Polaris Dawn''
            date_string = details_string[0].split(' ')
            # returns ['March','2023']
            year = date_string[1].strip()
            # returns '2023'
            month = month_dict.get(date_string[0])
            day = "null"

        # get tag id so we can use the anchor in the details link
        anchor = tag.get('id')
        return [[year, month, day], human_date, mission_string, anchor]
    else:
        pass



if __name__ == "__main__":
    process()
