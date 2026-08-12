#! python3

import clr
import math
import sys

from pyrevit import revit, DB, forms, script

# Use pyrevit's doc
doc = revit.doc

def ft_to_mm(val_ft):
    return round(val_ft * 304.8)

def ft_to_imperial_str(val_ft):
    total_inches = round(val_ft * 12)
    feet = int(total_inches // 12)
    inches = int(total_inches % 12)
    return f"{feet}' {inches}\""

def dist_2d(p1, p2):
    return math.sqrt((p1.X - p2.X)**2 + (p1.Y - p2.Y)**2)

def main():
    try:
        # 1. Pobranie wymiarów "Fluid Sales Dimension"
        all_dims = DB.FilteredElementCollector(doc)\
            .OfClass(DB.Dimension)\
            .WhereElementIsNotElementType()\
            .ToElements()

        target_dims = []
        for d in all_dims:
            try:
                dt = doc.GetElement(d.GetTypeId())
                if dt and dt.Name == "Fluid Sales Dimension":
                    target_dims.append(d)
            except:
                pass

        # 2. Pobranie tylko UMIESZCZONYCH pomieszczeń (Area > 0)
        all_rooms = DB.FilteredElementCollector(doc)\
            .OfCategory(DB.BuiltInCategory.OST_Rooms)\
            .WhereElementIsNotElementType()\
            .ToElements()

        valid_rooms = []
        for r in all_rooms:
            if hasattr(r, "Area") and r.Area > 0 and r.Location:
                loc_pt = getattr(r.Location, "Point", None)
                if loc_pt:
                    valid_rooms.append((r, loc_pt))

        # 3. Mapowanie Wymiar -> Najbliższe Room (bez limitu odległości)
        room_dim_map = {}
        debug_info = []

        for idx, dim in enumerate(target_dims):
            try:
                val = dim.Value
                if val is None or val == 0: continue

                pt = None
                if dim.Curve:
                    try:
                        pt = dim.Curve.Evaluate(0.5, True)
                    except:
                        pass
                if not pt:
                    pt = dim.Origin

                if not pt: continue

                min_dist = float('inf')
                closest_room = None

                for room, r_pt in valid_rooms:
                    d = dist_2d(pt, r_pt)
                    if d < min_dist:
                        min_dist = d
                        closest_room = room

                if closest_room:
                    r_id = closest_room.Id
                    if r_id not in room_dim_map:
                        room_dim_map[r_id] = []
                    room_dim_map[r_id].append(val)

                    if idx < 3:
                        r_pt = [p[1] for p in valid_rooms if p[0].Id == closest_room.Id][0]
                        debug_info.append(f"Wymiar #{idx+1} [X:{round(pt.X,1)}, Y:{round(pt.Y,1)}] -> Room {closest_room.Number} ({closest_room.Name}) [X:{round(r_pt.X,1)}, Y:{round(r_pt.Y,1)}] odleglosc:{round(min_dist,1)}ft")
            except Exception as ex:
                debug_info.append(f"Blad przy wymiarze #{idx}: {str(ex)}")

        # 4. Zapis do parametrów Room
        results_log = []
        results_log.append(f"--- DIAGNOSTYKA: Wymiary: {len(target_dims)} | Aktywne Rooms: {len(valid_rooms)} | Przypisano: {len(room_dim_map)} ---")
        results_log.extend(debug_info)

        with revit.Transaction("Sync Fluid Sales Dimensions"):
            for room in all_rooms:
                if not hasattr(room, "Area") or room.Area == 0:
                    continue # Pomijamy nieumieszczone pomieszczenia w raporcie końcowym

                dims = room_dim_map.get(room.Id, [])
                count = len(dims)

                p_w_mm = room.LookupParameter("Room_Width_mm")
                p_l_mm = room.LookupParameter("Room_Length_mm")
                p_w_imp = room.LookupParameter("Room_Width_Imperial")
                p_l_imp = room.LookupParameter("Room_Length_Imperial")

                if count == 0:
                    if p_w_mm: p_w_mm.Set(0)
                    if p_l_mm: p_l_mm.Set(0)
                    if p_w_imp: p_w_imp.Set("-")
                    if p_l_imp: p_l_imp.Set("-")
                    results_log.append(f"Room {room.Number} ({room.Name}): Brak wymiarow")

                elif count == 1:
                    w_val = dims[0]
                    if p_w_mm: p_w_mm.Set(ft_to_mm(w_val) / 304.8)
                    if p_w_imp: p_w_imp.Set(ft_to_imperial_str(w_val))
                    if p_l_mm: p_l_mm.Set(0)
                    if p_l_imp: p_l_imp.Set("-")
                    results_log.append(f"Room {room.Number} ({room.Name}): Width = {ft_to_mm(w_val)}mm")

                elif count >= 2:
                    dims_sorted = sorted(dims, reverse=True)
                    l_val = dims_sorted[0]
                    w_val = dims_sorted[1]

                    if p_w_mm: p_w_mm.Set(ft_to_mm(w_val) / 304.8)
                    if p_l_mm: p_l_mm.Set(ft_to_mm(l_val) / 304.8)
                    if p_w_imp: p_w_imp.Set(ft_to_imperial_str(w_val))
                    if p_l_imp: p_l_imp.Set(ft_to_imperial_str(l_val))

                    results_log.append(f"Room {room.Number} ({room.Name}): Width = {ft_to_mm(w_val)}mm, Length = {ft_to_mm(l_val)}mm")

        # Print output
        output = script.get_output()
        for log in results_log:
            output.print_md(log)
            print(log)

    except Exception as e:
        forms.alert(str(e), title="Error Syncing Dimensions")

if __name__ == "__main__":
    main()
