import dbus
import dbus.glib
import dbus.service
import unicodedata

from GTG.core import CoreConfig
from GTG.tools import dates

BUSNAME = CoreConfig.BUSNAME
BUSFACE = CoreConfig.BUSINTERFACE


def dsanitize(data):
    # Clean up a dict so that it can be transmitted through D-Bus
    for k, v in data.items():
        # Manually specify an arbitrary content type for empty Python arrays
        # because D-Bus can't handle the type conversion for empty arrays
        if not v and isinstance(v, list):
            data[k] = dbus.Array([], "s")
        # D-Bus has no concept of a null or empty value so we have to convert
        # None types to something else. I use an empty string because it has
        # the same behavior as None in a Python conditional expression
        elif v == None:
            data[k] = ""

    return data


def task_to_dict(task):
    # Translate a task object into a D-Bus dictionary
    return dbus.Dictionary(dsanitize({
          "id": task.get_id(),
          "status": task.get_status(),
          "title": task.get_title(),
          "duedate": str(task.get_due_date()),
          "startdate": str(task.get_start_date()),
          "donedate": str(task.get_closed_date()),
          "tags": task.get_tags_name(),
          "text": task.get_text(),
          "subtask": task.get_children(),
          }), signature="sv")


class DBusTaskWrapper(dbus.service.Object):

    # D-Bus service object that exposes GTG's task store to third-party apps
    def __init__(self, req, view_manager):
        # Attach the object to D-Bus
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(BUSNAME, bus=self.bus)
        dbus.service.Object.__init__(self, bus_name, BUSFACE)
        self.req = req
        self.view_manager = view_manager


    @dbus.service.method(BUSNAME,in_signature="s")
    def get_task_ids(self, status_string):
        # Retrieve a list of task ID values
        status = [s.strip() for s in status_string.split(',')]
        #need to convert the statuses to ascii (these are given in unicode)
        status = [unicodedata.normalize('NFKD', s).encode('ascii','ignore') \
                  for s in status]
        return self.req.get_tasks_list(status = status)

    @dbus.service.method(BUSNAME)
    def get_task(self, tid):
        # Retrieve a specific task by ID and return the data
        toret = task_to_dict(self.req.get_task(tid))
        return toret

    @dbus.service.method(BUSNAME)
    def get_tasks(self):
        # Retrieve a list of task data dicts
        return [self.get_task(id) for id in self.get_task_ids()]

    @dbus.service.method(BUSNAME, in_signature="as")
    def get_active_tasks(self, tags):
        # Retrieve a list of task data dicts
        return self.get_tasks_filtered(['active', 'workable'])

    @dbus.service.method(BUSNAME, in_signature="as")
    def get_task_ids_filtered(self, filters):
        tree = self.req.get_custom_tasks_tree()
        for filter in filters:
            tree.apply_filter(filter)
        return tree.get_all_keys()

    @dbus.service.method(BUSNAME, in_signature="as")
    def get_tasks_filtered(self, filters):
        tasks = self.get_task_ids_filtered(filters)
        if tasks:
            return [self.get_task(id) for id in tasks]
        else:
            return dbus.Array([], "s")

    @dbus.service.method(BUSNAME)
    def has_task(self, tid):
        return self.req.has_task(tid)

    @dbus.service.method(BUSNAME)
    def delete_task(self, tid):
        self.req.delete_task(tid)

    @dbus.service.method(BUSNAME, in_signature="sssssassas")
    def new_task(self, status, title, duedate, startdate, donedate, tags,
                 text, subtasks):
        # Generate a new task object and return the task data as a dict
        nt = self.req.new_task(tags=tags)
        for sub in subtasks:
            nt.add_child(sub)
        nt.set_status(status, donedate=dates.strtodate(donedate))
        nt.set_title(title)
        nt.set_due_date(dates.strtodate(duedate))
        nt.set_start_date(dates.strtodate(startdate))
        nt.set_text(text)
        return task_to_dict(nt)

    @dbus.service.method(BUSNAME)
    def modify_task(self, tid, task_data):
        # Apply supplied task data to the task object with the specified ID
        task = self.req.get_task(tid)
        task.set_status(task_data["status"], donedate=task_data["donedate"])
        task.set_title(task_data["title"])
        task.set_due_date(task_data["duedate"])
        task.set_start_date(task_data["startdate"])
        task.set_text(task_data["text"])

        for tag in task_data["tags"]:
            task.add_tag(tag)
        for sub in task_data["subtask"]:
            task.add_child(sub)
        return task_to_dict(task)

    @dbus.service.method(BUSNAME)
    def open_task_editor(self, tid):
        self.view_manager.open_task(tid)
        
    @dbus.service.method(BUSNAME, in_signature="ss")
    def open_new_task(self, title, description):
        nt = self.req.new_task(newtask=True)
        nt.set_title(title)
        if description != "":
            nt.set_text(description)
        uid = nt.get_id()
        self.view_manager.open_task(uid,thisisnew=True)

    @dbus.service.method(BUSNAME)
    def hide_task_browser(self):
        self.view_manager.hide_browser()

    @dbus.service.method(BUSNAME)
    def show_task_browser(self):
        self.view_manager.show_browser()
