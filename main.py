
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

1. normalise dates to compare with sysdate (on current month only due to output from the web page being a bit rubbish)
2. hash the response to see if it has changed first?
3. html + css
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

    generate_output(missions_array)

def generate_output(missions_array):
    """
    Generates html, filtered by sys date (should mak the sysdate part configurable?)
    :return:

    reference:  https://docs.python.org/3/library/time.html


	<tbody>
		<tr>
			<td></td>
			<td></td>
			<td></td>
			<td></td>
		</tr>
		<tr>
			<td></td>
			<td></td>
			<td></td>
			<td></td>
		</tr>
		<tr>
			<td></td>
			<td></td>
			<td></td>
			<td></td>
		</tr>
	</tbody>
</table>
    """
    #print(missions_array)
    table_head = """<table>
	<thead>
		<tr>
			<th>Date</th>
			<th>Mission</th>
			<th>Launch Pad</th>
			<th>More Information</th>
		</tr>
	</thead>
	<tbody>"""

    """
    [[['2022', '12', '31'], 'SpaceX Falcon 9, Transporter 6', 'january32023-spacexfalcon9transporter6', 'Launch was from launch pad SLC-40 with a launch time of 9:56 a.m. EST.'],...
    """
    current_time = time.time() # output = 1674993381.0381138
    for mission in missions_array:
        print(mission)
        #first assign any null days (no date defined in schedyule) to 1st of month for comparison only
        if mission[0][2] == "null":
            mission_day = 1
        else:
            mission_day = mission[0][2]
        print(mission_day)
        mission_date = datetime(int(mission[0][0]),int(mission[0][1]),int(mission_day),0,0)
        mission_date = calendar.timegm(mission_date.timetuple())
        if mission_date >= current_time:
            print("%s\n\n" % mission )
            sys.exit



def process_h2(tag):
    """
    Get date in a form where it can be compared with sysdate
    also return mission detail in an array
    tag.text = 'January 3, 2023 - SpaceX Falcon 9, Transporter 6' (an example)
                or January, 2023 - SpaceX Falcon 9, Transporter 6' (an example)
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

        """
        March 2023 - SpaceX Falcon 9, Polaris Dawn
        ['March 2023', 'SpaceX Falcon 9, Polaris Dawn']
        ['March 2023']
        """
        # 'January 3, 2023 - SpaceX Falcon 9, Transporter 6'
        # or March 2023 - SpaceX Falcon 9, Polaris Dawn
        details_string = details.split(" - ")  # normalise date for sysdate comparison
        # returns ['January 3, 2023 ',' SpaceX Falcon 9, Transporter 6']
        # or  ['March 2023', 'SpaceX Falcon 9, Polaris Dawn']
        mission_string = details_string[1].strip()
        # returns 'SpaceX Falcon 9, Transporter 6'
        # or 'SpaceX Falcon 9, Polaris Dawn'
        date_string = details_string[0].split(',')
        # returns ['January 3',' 2023 ']
        # or  ['March 2023', 'SpaceX Falcon 9, Polaris Dawn'] ...
        try:
            year = date_string[1].strip()
            # returns '2023'
        except:
            # ['March 2023']
            year = date_string[0].split(' ')[1]
            # returns
        try:
            month_day = date_string[0].split(' ')
            # returns ['January',' 3']
            month = month_dict.get(month_day[0])
            day = month_day[1]
            if len(day) == 1:
                #pad with leading zero
                day = "0%s" % day
        except IndexError:
            day = 'null'
        # get tag id so we can use the anchor in the details link
        anchor = tag.get('id')
        return [[year, month, day], mission_string, anchor]
    else:
        pass



if __name__ == "__main__":
    process()
