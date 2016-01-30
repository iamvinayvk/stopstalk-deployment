"""
    Copyright (c) 2015-2016 Raj Patel(raj454raj@gmail.com), StopStalk

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
"""

import time
from datetime import date, datetime
from gluon import current, IMG, DIV, TABLE, THEAD, \
                  TBODY, TR, TH, TD, A, SPAN, INPUT, \
                  TEXTAREA, SELECT, OPTION, URL

# -----------------------------------------------------------------------------
def get_link(site, handle):
    """
        Get the URL of site_handle
    """

    return current.SITES[site] + handle

# -----------------------------------------------------------------------------
def get_friends(user_id):
    """
        Friends of user_id (including custom friends)

        @Return: (list of friend_ids, list of custom_friend_ids)
    """

    db = current.db
    cftable = db.custom_friend
    atable = db.auth_user
    ftable = db.friends

    # Retrieve custom friends
    query = (cftable.user_id == user_id)
    custom_friends = db(query).select(cftable.id)
    custom_friends = [x["id"] for x in custom_friends]

    # Retrieve friends
    query = (ftable.user_id == user_id)
    friends = db(query).select(ftable.friend_id)
    friends = [x["friend_id"] for x in friends]

    return friends, custom_friends

# ----------------------------------------------------------------------------
def get_accepted_streak(handle):
    """
        Function that returns current streak of accepted solutions
    """

    db = current.db
    sql_query = """
                    SELECT COUNT( * )
                    FROM  `submission`
                    WHERE stopstalk_handle='%s'
                    AND time_stamp > (SELECT time_stamp
                                        FROM  `submission`
                                        WHERE stopstalk_handle='%s'
                                          AND STATUS <>  'AC'
                                        ORDER BY time_stamp DESC
                                        LIMIT 1);
                """ % (handle, handle)

    streak = db.executesql(sql_query)
    return streak[0][0]

# ----------------------------------------------------------------------------
def get_max_accepted_streak(handle):
    """
        Return the max accepted solution streak
    """
    db = current.db
    sql_query = """
                    SELECT status
                    FROM `submission`
                    WHERE stopstalk_handle='%s'
                    ORDER BY time_stamp;
                """ % (handle)
    rows = db.executesql(sql_query)

    prev = None
    streak = max_streak = 0

    for status in rows:
        if prev is None:
            if status[0] == "AC":
                streak = 1
        elif prev == "AC" and status[0] == "AC":
            streak += 1
        elif prev != "AC" and status[0] == "AC":
            streak = 1
        elif prev == "AC" and status[0] != "AC":
            max_streak = max(max_streak, streak)
            streak = 0
        prev = status[0]

    max_streak = max(max_streak, streak)
    return max_streak

# ----------------------------------------------------------------------------
def get_max_streak(handle):
    """
        Get the maximum of all streaks
    """

    db = current.db

    # Build the complex SQL query
    sql_query = """
                    SELECT time_stamp, COUNT(*)
                    FROM submission
                    WHERE submission.stopstalk_handle='%s'
                    GROUP BY DATE(submission.time_stamp), submission.status;
                 """ % (handle)

    row = db.executesql(sql_query)
    streak = 0
    max_streak = 0
    prev = curr = None
    total_submissions = 0

    for i in row:

        total_submissions += i[1]
        if prev is None and streak == 0:
            prev = time.strptime(str(i[0]), "%Y-%m-%d %H:%M:%S")
            prev = date(prev.tm_year, prev.tm_mon, prev.tm_mday)
            streak = 1
        else:
            curr = time.strptime(str(i[0]), "%Y-%m-%d %H:%M:%S")
            curr = date(curr.tm_year, curr.tm_mon, curr.tm_mday)

            if (curr - prev).days == 1:
                streak += 1
            elif curr != prev:
                streak = 1

            prev = curr

        if streak > max_streak:
            max_streak = streak

    today = datetime.today().date()

    # There are no submissions in the database for this user
    if prev is None:
        return (0,) * 4

    # Check if the last streak is continued till today
    if (today - prev).days > 1:
        streak = 0

    return max_streak, total_submissions, streak, len(row)

# ----------------------------------------------------------------------------
def compute_row(user, custom=False, update_flag=False):
    """
        Computes rating and retrieves other
        information of the specified user
    """

    tup = get_max_streak(user.stopstalk_handle)
    max_streak = tup[0]
    total_submissions = tup[1]

    db = current.db
    stable = db.submission

    # Find the total solved problems(Lesser than total accepted)
    query = (stable.stopstalk_handle == user.stopstalk_handle)
    query &= (stable.status == "AC")
    solved = db(query).select(stable.problem_name, distinct=True)
    solved = len(solved)

    today = datetime.today().date()
    start = datetime.strptime(current.INITIAL_DATE,
                              "%Y-%m-%d %H:%M:%S").date()
    if custom:
        table = db.custom_friend
    else:
        table = db.auth_user

    query = (table.stopstalk_handle == user.stopstalk_handle)
    record = db(query).select(table.per_day, table.rating).first()
    if record.per_day is None or \
       record.per_day == 0.0:
        per_day = total_submissions * 1.0 / (today - start).days
    else:
        per_day = record.per_day

    curr_per_day = total_submissions * 1.0 / (today - start).days
    diff = "%0.5f" % (curr_per_day - per_day)
    diff = float(diff)

    # I am not crazy. This is to solve the problem
    # if diff is -0.0
    if diff == 0.0:
        diff = 0.0

    if total_submissions == 0:
        rating = 0
    else:
        # Unique rating formula
        # @ToDo: Improvement is always better
        rating = (curr_per_day - per_day) * 100000 + \
                  max_streak * 50 + \
                  solved * 100 + \
                  (solved * 100.0 / total_submissions) * 40 + \
                  (total_submissions - solved) * 10 + \
                  per_day * 150
    rating = int(rating)

    if record.rating != rating:
        rating_diff = rating - int(record.rating)
        if update_flag:
            # Update the rating ONLY when the function is called by run-it5.py
            query = (table.stopstalk_handle == user.stopstalk_handle)
            db(query).update(per_day=per_day,
                             rating=rating)
    else:
        rating_diff = 0

    return (user.first_name + " " + user.last_name,
            user.stopstalk_handle,
            user.institute,
            rating,
            diff,
            custom,
            rating_diff)

# -----------------------------------------------------------------------------
def materialize_form(form, fields):
    """
        Change layout of SQLFORM forms
    """

    form.add_class("form-horizontal center")
    main_div = DIV(_class="center")

    for field_id, label, controls, field_help in fields:
        curr_div = DIV(_class="row")
        input_field = None
        _controls = controls

        try:
            _name = controls.attributes["_name"]
        except:
            _name = ""
        try:
            _type = controls.attributes["_type"]
        except:
            _type = "string"

        try:
            _id = controls.attributes["_id"]
        except:
            _id = ""

        if isinstance(controls, INPUT):
            if _type == "file":
                # Layout for file type inputs
                input_field = DIV(DIV(SPAN("Upload"),
                                      INPUT(_type=_type,
                                            _id=_id),
                                      _class="btn"),
                                  DIV(INPUT(_type="text",
                                            _class="file-path",
                                            _placeholder=label.components[0]),
                                      _class="file-path-wrapper"),
                                  _class="col input-field file-field offset-s3 s6")
        if isinstance(controls, SPAN):
            # Mostly for ids which cannot be edited by user
            _controls = INPUT(_value=controls.components[0],
                              _id=_id,
                              _name=_name,
                              _disabled="disabled")
        elif isinstance(controls, TEXTAREA):
            # Textarea inputs
            try:
                _controls = TEXTAREA(controls.components[0],
                                     _name=_name,
                                     _id=_id,
                                     _class="materialize-textarea text")
            except IndexError:
                _controls = TEXTAREA(_name=_name,
                                     _id=_id,
                                     _class="materialize-textarea text")
        elif isinstance(controls, SELECT):
            # Select inputs
            _controls = SELECT(OPTION(label, _value=""),
                               _name=_name,
                               _class="browser-default",
                               *controls.components[1:])
            # Note now label will be the first element
            # of Select input whose value would be ""
            label = ""
        elif isinstance(controls, A):
            # For the links in the bottom while updating tables like auth_user
            label = ""
        elif isinstance(controls, INPUT) is False:
            # If the values are readonly
            _controls = INPUT(_value=controls,
                              _name=_name,
                              _disabled="")

        if input_field is None:
            input_field = DIV(_controls, label,
                              _class="input-field col offset-s3 s6")

        curr_div.append(input_field)
        main_div.append(curr_div)

    return main_div

# -----------------------------------------------------------------------------
def render_table(submissions):
    """
        Create the HTML table from submissions
    """

    status_dict = {"AC": "Accepted",
                   "WA": "Wrong Answer",
                   "TLE": "Time Limit Exceeded",
                   "MLE": "Memory Limit Exceeded",
                   "RE": "Runtime Error",
                   "CE": "Compile Error",
                   "SK": "Skipped",
                   "HCK": "Hacked",
                   "OTH": "Others"}

    table = TABLE(_class="striped centered")
    table.append(THEAD(TR(TH("User Name"),
                          TH("Site"),
                          TH("Site Handle"),
                          TH("Time of submission"),
                          TH("Problem"),
                          TH("Language"),
                          TH("Status"),
                          TH("Points"),
                          TH("View Code"))))

    tbody = TBODY()
    for submission in submissions:
        tr = TR()
        append = tr.append

        person_id = submission.custom_user_id
        if submission.user_id:
            person_id = submission.user_id

        append(TD(A(person_id.first_name + " " + person_id.last_name,
                    _href=URL("user", "profile",
                              args=[submission.stopstalk_handle]),
                    _target="_blank")))
        append(TD(submission.site))
        append(TD(A(submission.site_handle,
                    _href=get_link(submission.site,
                                   submission.site_handle),
                    _target="_blank")))
        append(TD(submission.time_stamp))
        append(TD(A(submission.problem_name,
                    _href=URL("problems",
                              "index",
                              vars={"pname": submission.problem_name,
                                    "plink": submission.problem_link}),
                    _target="_blank")))
        append(TD(submission.lang))
        append(TD(IMG(_src=URL("static",
                               "images/" + submission.status + ".jpg"),
                      _title=status_dict[submission.status],
                      _style="height: 25px; width: 25px;")))
        append(TD(submission.points))

        if submission.view_link:
            append(TD(A("View",
                        _href=submission.view_link,
                        _class="btn waves-light waves-effect",
                        _style="background-color: #FF5722",
                        _target="_blank")))
        else:
            append(TD())

        tbody.append(tr)
    table.append(tbody)
    return table

# END =========================================================================
