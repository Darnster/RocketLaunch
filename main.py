
from bs4 import BeautifulSoup
import requests
import sys

"""
https://www.pluralsight.com/guides/web-scraping-with-beautiful-soup

What this code does...

It queries the Florida launch timetable page and returns the results in an easy to read summary as a table.
It then emails the results when the page has identified as being updated.

TO DO:
------

1. normalise dates to compare with sysdate (on current month only due to output from the web page being a bit rubbish)
2. hash the response to see if it has changed first?
3. html + css
4. email output to me when something changes
5. schedule it somewhere (on my phone)
"""


def process():
    content = requests.get("https://floridareview.co.uk/things-to-do/current-launch-schedule")
    # print(content)
    soup = BeautifulSoup(content.text, 'html.parser')
    tags = soup.find_all(['h2', 'p'])  # Extract and return first occurrence of h2
    # print(tags)  # Print row with HTML formatting

    # need to build an array of arrays here, e.g. [[date],mission_details,launch pad, link] link -> #march72023-spacexfalcon9intelsat40e
    main_array = []
    ctrl_flag = False
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
                print(this_mission)
                ctrl_flag = False


def process_h2(tag):
    """
    Get date in a form where it can be compared with sysdate
    also return mission detail in an array
    tag.text = 'January 3, 2023 - SpaceX Falcon 9, Transporter 6' (an example)
                or January, 2023 - SpaceX Falcon 9, Transporter 6' (an example)
    :param tag:
    :return: array [[<date>], [mission]]
    """
    month_dict = {
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
        
        reference:  https://docs.python.org/3/library/time.html
        """
        details_string = details.split(" - ")  # normalise date for sysdate comparison
        mission_string = details_string[1].strip()
        # returns ['January 3, 2023 ',' SpaceX Falcon 9, Transporter 6']
        date_string = details_string[0].split(',')
        # returns ['January 3',' 2023 ']
        try:
            year = date_string[1].strip()
            # returns '2023'
        except:
            # January, 2023 - SpaceX Falcon 9, Transporter 6   *** no day included ***
            year = date_string[0].split(' ')[1]
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
        return [[day, month, year], mission_string]
    else:
        pass



if __name__ == "__main__":
    process()
