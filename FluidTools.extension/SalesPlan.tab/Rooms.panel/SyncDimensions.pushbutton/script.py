#! python3

import sys
import clr
import math

from pyrevit import revit, DB, forms, script

doc = revit.doc

def get_dim_value_str(dim):
    try:
        if dim.ValueString:
            return dim.ValueString.replace(" mm", "").replace("mm", "").strip()
    except:
        pass
    val_ft = dim.Value
    if val_ft:
        return str(int(round(val_ft * 304.8)))
    return ""

def ft_to_imperial_str(val_ft):
    if not val_ft:
        return ""
    total_inches = round(val_ft * 12)
    feet = int(total_inches // 12)
    inches = int(total_inches % 12)
    return f"{feet}' {inches}\""

def is_horizontal_dim(dim):
    try:
        if dim.Curve:
            dir_vec = dim.Curve.Direction
            return abs(dir_vec.X) > abs(dir_vec.Y)
    except:
        pass
    return True

def get_dim_point(dim):
    try:
        if dim.Curve and dim.Curve.IsBound:
            return dim.Curve.Evaluate(0.5, True)
    except:
        pass
    try:
        return dim.Origin
    except:
        return None

def clear_param(param):
    if not param:
        return
    try:
        param.ClearValue()
    except:
        if param.StorageType == DB.StorageType.String:
            param.Set("")

def main():
    try:
        # 1. Map wall boundaries to rooms
        wall_to_rooms = {}
        spatial_opts = DB.SpatialElementBoundaryOptions()

        all_rooms = DB.FilteredElementCollector(doc)\
            .OfCategory(DB.BuiltInCategory.OST_Rooms)\
            .WhereElementIsNotElementType()\
            .ToElements()

        valid_rooms = [r for r in all_rooms if hasattr(r, "Area") and r.Area > 0]
        room_bboxes = {r.Id: r.get_BoundingBox(None) for r in valid_rooms}

        for room in valid_rooms:
            boundary_segments = room.GetBoundarySegments(spatial_opts)
            if boundary_segments:
                for segment_list in boundary_segments:
                    for seg in segment_list:
                        elem_id = seg.ElementId
                        if elem_id != DB.ElementId.InvalidElementId:
                            if elem_id not in wall_to_rooms:
                                wall_to_rooms[elem_id] = set()
                            wall_to_rooms[elem_id].add(room.Id)

        # 2. Collect target dimensions
        all_dims = DB.FilteredElementCollector(doc)\
            .OfClass(DB.Dimension)\
            .WhereElementIsNotElementType()\
            .ToElements()

        target_dims = [d for d in all_dims if d.DimensionType and d.DimensionType.Name == "Fluid Sales Dimension"]

        # 3. Match dimensions to rooms by level and orientation
        room_dim_map = {}

        for dim in target_dims:
            val_ft = dim.Value
            if val_ft is None or val_ft == 0:
                continue

            dim_view = doc.GetElement(dim.OwnerViewId)
            dim_level_id = dim_view.GenLevel.Id if (dim_view and hasattr(dim_view, "GenLevel") and dim_view.GenLevel) else None

            matched_room_ids = set()
            try:
                refs = dim.References
                if refs:
                    for r in refs:
                        if r.ElementId in wall_to_rooms:
                            matched_room_ids.update(wall_to_rooms[r.ElementId])
            except:
                pass

            if dim_level_id:
                matched_room_ids = {r_id for r_id in matched_room_ids if doc.GetElement(r_id).Level.Id == dim_level_id}

            assigned_room_id = None
            if len(matched_room_ids) == 1:
                assigned_room_id = list(matched_room_ids)[0]
            else:
                pt = get_dim_point(dim)
                if pt:
                    level_rooms = [r for r in valid_rooms if (not dim_level_id or r.Level.Id == dim_level_id)]
                    candidates = matched_room_ids if len(matched_room_ids) > 1 else [r.Id for r in level_rooms]

                    for r_id in candidates:
                        bbox = room_bboxes.get(r_id)
                        if bbox and (bbox.Min.X <= pt.X <= bbox.Max.X) and (bbox.Min.Y <= pt.Y <= bbox.Max.Y):
                            assigned_room_id = r_id
                            break

            if assigned_room_id:
                if assigned_room_id not in room_dim_map:
                    room_dim_map[assigned_room_id] = {'horiz': [], 'vert': []}

                if is_horizontal_dim(dim):
                    room_dim_map[assigned_room_id]['horiz'].append(dim)
                else:
                    room_dim_map[assigned_room_id]['vert'].append(dim)

        # 4. Write to room parameters
        with revit.Transaction("Sync Fluid Sales Dimensions"):
            for room in valid_rooms:
                d_dict = room_dim_map.get(room.Id, {'horiz': [], 'vert': []})

                p_w_mm = room.LookupParameter("Room_Width_mm")
                p_l_mm = room.LookupParameter("Room_Length_mm")
                p_w_imp = room.LookupParameter("Room_Width_Imperial")
                p_l_imp = room.LookupParameter("Room_Length_Imperial")

                # Width (X-axis)
                if d_dict['horiz']:
                    d_horiz = d_dict['horiz'][0]
                    w_mm_str = get_dim_value_str(d_horiz)
                    w_imp_str = ft_to_imperial_str(d_horiz.Value)
                    if p_w_mm:
                        try:
                            p_w_mm.Set(float(w_mm_str))
                        except:
                            pass
                    if p_w_imp:
                        p_w_imp.Set(w_imp_str)
                else:
                    clear_param(p_w_mm)
                    clear_param(p_w_imp)

                # Length (Y-axis)
                if d_dict['vert']:
                    d_vert = d_dict['vert'][0]
                    l_mm_str = get_dim_value_str(d_vert)
                    l_imp_str = ft_to_imperial_str(d_vert.Value)
                    if p_l_mm:
                        try:
                            p_l_mm.Set(float(l_mm_str))
                        except:
                            pass
                    if p_l_imp:
                        p_l_imp.Set(l_imp_str)
                else:
                    clear_param(p_l_mm)
                    clear_param(p_l_imp)

        # Output feedback
        output = script.get_output()
        output.print_md("### Synchronization Complete")
        output.print_md(f"**Valid Rooms Processed:** {len(valid_rooms)}")
        output.print_md(f"**Dimensions Mapped:** {sum(len(d['horiz']) + len(d['vert']) for d in room_dim_map.values())}")

    except Exception as e:
        forms.alert(str(e), title="Error Syncing Dimensions")

if __name__ == "__main__":
    main()
