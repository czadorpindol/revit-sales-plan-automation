#! python3

import csv
from pyrevit import revit, DB, forms

doc = revit.doc
save_path = forms.save_file(file_ext='csv', default_name='Sales_Plan_Dimensions.csv', title='Save Sales Plan Dimensions')

if save_path:
    all_rooms = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()
    valid_rooms = [r for r in all_rooms if hasattr(r, "Area") and r.Area > 0]
    valid_rooms.sort(key=lambda r: (r.Level.Name if r.Level else "", r.Number))

    headers = ["Level", "Number", "Name", "Width (mm)", "Length (mm)", "Width (ft/in)", "Length (ft/in)"]
    rows = []

    for room in valid_rooms:
        lvl = room.Level.Name if room.Level else "-"
        w_mm = room.LookupParameter("Room_Width_mm")
        l_mm = room.LookupParameter("Room_Length_mm")
        w_imp = room.LookupParameter("Room_Width_Imperial")
        l_imp = room.LookupParameter("Room_Length_Imperial")

        val_w_mm = int(w_mm.AsDouble()) if (w_mm and w_mm.HasValue and w_mm.AsDouble() > 0) else ""
        val_l_mm = int(l_mm.AsDouble()) if (l_mm and l_mm.HasValue and l_mm.AsDouble() > 0) else ""
        val_w_imp = w_imp.AsString() if (w_imp and w_imp.HasValue) else ""
        val_l_imp = l_imp.AsString() if (l_imp and l_imp.HasValue) else ""

        rows.append([lvl, room.Number, room.LookupParameter("Name").AsString() or "", val_w_mm, val_l_mm, val_w_imp, val_l_imp])

    try:
        with open(save_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)
            writer.writerows(rows)
        forms.alert('Export successful!\nFile: {}'.format(save_path))
    except Exception as e:
        forms.alert('Export failed:\n{}'.format(str(e)))
