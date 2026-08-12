import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')

from Autodesk.Revit.DB import *
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument

def ft_to_mm(val_ft):
    return round(val_ft * 304.8)

def ft_to_imperial_str(val_ft):
    total_inches = round(val_ft * 12)
    feet = int(total_inches // 12)
    inches = int(total_inches % 12)
    return f"{feet}' {inches}\""

# 1. Pobranie wymiarów stylu "Fluid Sales Dimension"
all_dims = FilteredElementCollector(doc)\
    .OfClass(Dimension)\
    .WhereElementIsNotElementType()\
    .ToElements()

target_dims = [d for d in all_dims if d.DimensionType.Name == "Fluid Sales Dimension"]

# 2. Mapowanie Wymiar -> Room (przez punkt środkowy)
room_dim_map = {}

for dim in target_dims:
    try:
        curve = dim.Curve
        mid_point = curve.Evaluate(0.5, True)
        
        # Pobieramy Room w punkcie środkowym wymiaru
        room = doc.GetRoomAtPoint(mid_point)
        if room:
            r_id = room.Id
            if r_id not in room_dim_map:
                room_dim_map[r_id] = []
            room_dim_map[r_id].append(dim.Value)
    except:
        continue

# 3. Pobranie wszystkich Room w modelu
all_rooms = FilteredElementCollector(doc)\
    .OfCategory(BuiltInCategory.OST_Rooms)\
    .WhereElementIsNotElementType()\
    .ToElements()

TransactionManager.Instance.EnsureInTransaction(doc)

results_log = []

for room in all_rooms:
    dims = room_dim_map.get(room.Id, [])
    count = len(dims)
    
    p_w_mm = room.LookupParameter("Room_Width_mm")
    p_l_mm = room.LookupParameter("Room_Length_mm")
    p_w_imp = room.LookupParameter("Room_Width_Imperial")
    p_l_imp = room.LookupParameter("Room_Length_Imperial")
    
    if count == 0:
        # Brak wymiarów
        if p_w_mm: p_w_mm.Set(0)
        if p_l_mm: p_l_mm.Set(0)
        if p_w_imp: p_w_imp.Set("-")
        if p_l_imp: p_l_imp.Set("-")
        results_log.append(f"Room {room.Number}: Brak wymiarów")
        
    elif count == 1:
        # 1 wymiar (Width)
        w_val = dims[0]
        if p_w_mm: p_w_mm.Set(ft_to_mm(w_val) / 304.8) # Wartość wewnętrzna w stopach
        if p_w_imp: p_w_imp.Set(ft_to_imperial_str(w_val))
        if p_l_mm: p_l_mm.Set(0)
        if p_l_imp: p_l_imp.Set("-")
        results_log.append(f"Room {room.Number}: Przypisano 1 wymiar (Width)")
        
    elif count >= 2:
        # 2 lub więcej wymiarów: Większy = Length, Mniejszy = Width
        dims_sorted = sorted(dims, reverse=True)
        l_val = dims_sorted[0]
        w_val = dims_sorted[1]
        
        if p_w_mm: p_w_mm.Set(ft_to_mm(w_val) / 304.8)
        if p_l_mm: p_l_mm.Set(ft_to_mm(l_val) / 304.8)
        if p_w_imp: p_w_imp.Set(ft_to_imperial_str(w_val))
        if p_l_imp: p_l_imp.Set(ft_to_imperial_str(l_val))
        
        status = "2 wymiary przypisane" if count == 2 else f"Uwaga: Zaleziono {count} wymiarów, wzięto 2 największe"
        results_log.append(f"Room {room.Number}: {status}")

TransactionManager.Instance.TransactionTaskDone()

OUT = results_log
