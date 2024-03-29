import yayv

def Dayparts(*args):
  return yayv.ByExample(
        "- name: UNIQUE\n"
        "  row: REQUIRED\n"
        "  col: REQUIRED\n"
        "  rowspan: OPTIONAL\n"
        "  colspan: OPTIONAL\n")

def Classes():
  return yayv.ByExample(
        "- name: REQUIRED\n"
        "  id: AUTO_INC\n"
        "  instructor: OPTIONAL\n"
        "  max_enrollment: REQUIRED\n"
        "  prerequisites:\n"
        "    - current_grade: OPTIONAL\n"
        "      email: OPTIONAL\n"
        "      group: OPTIONAL\n"
        "  excludegroups:\n"
        "    - OPTIONAL\n"
        "  schedule:\n"
        "    - daypart: REQUIRED\n"
        "      location: REQUIRED\n"
        "  description: OPTIONAL\n"
        "  donation: OPTIONAL\n"
        "  exclude_from_catalog: OPTIONAL\n"
        "  exclude_from_attendance: OPTIONAL\n"
        "  owners:\n"
        "    - OPTIONAL\n"
        "  open_enrollment: OPTIONAL\n"
        "  fitness: OPTIONAL\n")

def Students():
  return yayv.ByExample(
        "- email: UNIQUE\n"
        "  first: REQUIRED\n"
        "  last: REQUIRED\n"
        "  current_grade: REQUIRED\n"
        "  current_homeroom: REQUIRED\n"
        "  edtechid: OPTIONAL\n")

def Teachers():
  return yayv.ByExample(
        "- email: UNIQUE\n"
        "  first: REQUIRED\n"
        "  last: REQUIRED\n"
        "  current_homeroom: OPTIONAL\n")

def AutoRegister():
  return yayv.ByExample(
        "- class: OPTIONAL\n" # for human use
        "  class_id: REQUIRED\n" # should match id from Classes
        "  applies_to:\n"
        "    - current_grade: OPTIONAL\n"
        "      email: OPTIONAL\n"
        "      group: OPTIONAL\n"
        "  id: OPTIONAL\n"
        "  exempt:\n"
        "    - OPTIONAL\n")

def Requirements():
  return yayv.ByExample(
        "- name: REQUIRED\n"
        "  applies_to:\n"
        "    - current_grade: OPTIONAL\n"
        "      email: OPTIONAL\n"
        "      group: OPTIONAL\n"
        "  id: AUTO_INC\n"
        "  exempt:\n"
        "    - OPTIONAL\n"
        "  class_or_group_options:\n"
        "    - \n"
        "      - OPTIONAL\n")

def ClassGroups():
  return yayv.ByExample(
        "- name: REQUIRED\n"
        "  id: AUTO_INC\n"
        "  classes:\n"
        "    - name: OPTIONAL\n" # for human use
        "      id: REQUIRED\n")

def StudentGroups():
  return yayv.ByExample(
        "- group_name: REQUIRED\n"
        "  emails:\n"
        "    - REQUIRED\n")

def ServingRules():
  return yayv.ByExample(
        "- name: REQUIRED\n"
        "  allow:\n"
        "    - current_grade: OPTIONAL\n"
        "      current_homeroom: OPTIONAL\n"
        "      email: OPTIONAL\n")

def Links():
  return yayv.ByExample(
        "- name: REQUIRED\n"
        "  url: REQUIRED\n")
