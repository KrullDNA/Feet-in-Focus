#!/usr/bin/env python3
"""
Minimal GHX test files — isolates which component causes NullReferenceException.

Generates four tiny .ghx files:
  test_slider.ghx   — 1 Number Slider only
  test_panel.ghx    — 1 Panel only
  test_group.ghx    — 1 Group only
  test_python.ghx   — 1 GHPython (x input → a output, code: a=x)
  test_slider_python.ghx — Slider wired into GHPython (like the real file)

Drop each into Grasshopper one at a time.
The first one that crashes tells us which component type is wrong.
"""

import uuid, xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

GUID_SLIDER   = "57da07bd-ecab-415d-9d86-af36d7073abc"
GUID_PANEL    = "59e0b89a-e487-49f8-bab8-b5bab16be14c"
GUID_GHPYTHON = "410755b1-224a-4c1e-a407-bf32fb45ea7e"
GUID_GROUP    = "c552a431-af5b-46a9-a8a4-0fcbc27ef596"
NO_HINT       = "35915213-5534-4277-81b8-1bdc9e7383d2"

def ng(): return str(uuid.uuid4()).lower()

class Chunk:
    def __init__(self, name, index=None):
        self.name = name; self.index = index
        self.items = []; self.chunks = []
    def add_item(self, name, type_name, type_code, value, index=None):
        self.items.append((name, type_name, str(type_code), value, index)); return self
    def add_chunk(self, c): self.chunks.append(c); return c
    def str_(self, n, v, idx=None):  return self.add_item(n,"gh_string","10",str(v),idx)
    def guid_(self, n, v, idx=None): return self.add_item(n,"gh_guid","9",str(v),idx)
    def bool_(self, n, v):           return self.add_item(n,"gh_bool","1","true" if v else "false")
    def int_(self, n, v, idx=None):  return self.add_item(n,"gh_int32","3",str(v),idx)
    def dbl_(self, n, v):            return self.add_item(n,"gh_double","6",str(v))
    def rect_(self, n, x, y, w, h):  return self.add_item(n,"gh_drawing_rectanglef","35",("XYWH",x,y,w,h))
    def pt_(self, n, x, y):          return self.add_item(n,"gh_drawing_pointf","31",("XY",x,y))
    def color_(self, n, a, r, g, b): return self.add_item(n,"gh_drawing_color","36",("ARGB",f"{a};{r};{g};{b}"))

    def to_element(self):
        attrs = {"name": self.name}
        if self.index is not None: attrs["index"] = str(self.index)
        el = ET.Element("chunk", attrs)
        if self.items:
            ie_el = ET.SubElement(el, "items", {"count": str(len(self.items))})
            for (nm, tn, tc, val, ix) in self.items:
                a = {"name": nm, "type_name": tn, "type_code": tc}
                if ix is not None: a["index"] = str(ix)
                ie = ET.SubElement(ie_el, "item", a)
                if isinstance(val, tuple):
                    tag = val[0]
                    if tag == "ARGB":
                        ET.SubElement(ie, "ARGB").text = val[1]
                    elif tag == "XYWH":
                        for attr, v in zip("XYWH", val[1:]):
                            ET.SubElement(ie, attr).text = str(int(v))
                    elif tag == "XY":
                        for attr, v in zip("XY", val[1:]):
                            ET.SubElement(ie, attr).text = str(int(v))
                else:
                    ie.text = str(val)
        if self.chunks:
            ch_el = ET.SubElement(el, "chunks", {"count": str(len(self.chunks))})
            for c in self.chunks: ch_el.append(c.to_element())
        return el


def attr(x, y, w, h):
    ch = Chunk("Attributes")
    ch.rect_("Bounds", x, y, w, h)
    ch.pt_("Pivot", x+w//2, y+h//2)
    ch.bool_("Selected", False)
    return ch


def make_slider():
    inst = ng()
    obj = Chunk("Object"); obj.guid_("GUID", GUID_SLIDER); obj.str_("Name","Number Slider")
    cont = Chunk("Container")
    cont.str_("Description","Test slider"); cont.guid_("InstanceGuid",inst)
    cont.bool_("Locked",False)
    cont.dbl_("Slider_Max",10.0); cont.dbl_("Slider_Min",0.0)
    cont.int_("Slider_Type",1); cont.dbl_("Slider_Value",5.0)
    cont.int_("Slider_Decimals",1)
    cont.str_("Name","Number Slider"); cont.str_("NickName","Slider")
    cont.int_("SourceCount",0)
    cont.add_chunk(attr(50,50,200,20))
    obj.add_chunk(cont)
    return obj, inst


def make_panel():
    inst = ng()
    obj = Chunk("Object"); obj.guid_("GUID", GUID_PANEL); obj.str_("Name","Panel")
    cont = Chunk("Container")
    cont.str_("Description","Test panel"); cont.guid_("InstanceGuid",inst)
    cont.bool_("Locked",False)
    cont.str_("Name","Panel"); cont.str_("NickName","Panel")
    cont.int_("SourceCount",0); cont.str_("UserText","Hello"); cont.bool_("WrapText",True)
    cont.add_chunk(attr(50,50,200,50))
    obj.add_chunk(cont)
    return obj, inst


def make_group(member_guids):
    inst = ng()
    obj = Chunk("Object"); obj.guid_("GUID", GUID_GROUP); obj.str_("Name","Group")
    cont = Chunk("Container")
    cont.int_("Border",1); cont.color_("Colour",150,130,180,220)
    cont.str_("Description","A group of Grasshopper objects")
    for i, g in enumerate(member_guids): cont.guid_("ID",g,i)
    cont.int_("ID_Count",len(member_guids)); cont.guid_("InstanceGuid",inst)
    cont.str_("Name","Test Group"); cont.str_("NickName","Test Group")
    cont.add_chunk(Chunk("Attributes"))  # empty — GH auto-sizes groups
    obj.add_chunk(cont)
    return obj, inst


def make_python(src_guid=None):
    inst = ng(); in_guid = ng(); out_guid = ng()
    obj = Chunk("Object"); obj.guid_("GUID", GUID_GHPYTHON); obj.str_("Name","Python Script")
    cont = Chunk("Container")
    cont.str_("CodeInput","a = x")
    cont.str_("Description","Minimal test GHPython component")
    cont.bool_("HideCodeInput",True); cont.bool_("HideOutput",True)
    cont.guid_("InstanceGuid",inst)
    cont.bool_("IsAdvancedMode",False)
    cont.bool_("Locked",False)
    cont.bool_("MarshalOutGuids",False)
    cont.str_("Name","Test Python"); cont.str_("NickName","TestPy")

    # Input param
    pi = Chunk("param_input"); pi.int_("param_count",1)
    p = Chunk("param", index=0)
    p.str_("Description","test input"); p.guid_("InstanceGuid",in_guid)
    p.str_("Name","x"); p.str_("NickName","x"); p.bool_("Optional",True)
    p.int_("Access",0)
    srcs = [src_guid] if src_guid else []
    p.int_("SourceCount", len(srcs))
    for si, sg in enumerate(srcs):
        p.guid_("Source", sg, si)
    th = Chunk("TypeHint"); th.guid_("TypeHintID", NO_HINT); p.add_chunk(th)
    pi.add_chunk(p); cont.add_chunk(pi)

    # Output param
    po = Chunk("param_output"); po.int_("param_count",1)
    q = Chunk("param", index=0)
    q.str_("Description","test output"); q.guid_("InstanceGuid",out_guid)
    q.str_("Name","a"); q.str_("NickName","a"); q.bool_("Optional",False)
    q.int_("SourceCount",0)
    po.add_chunk(q); cont.add_chunk(po)

    cont.add_chunk(attr(280,50,200,60))
    obj.add_chunk(cont)
    return obj, inst, out_guid, in_guid


def build_ghx(objects):
    root = ET.Element("Archive", name="Root")
    # ArchiveVersion 0.2.2 (modern GH format)
    items_root = ET.SubElement(root, "items", count="1")
    av = ET.SubElement(items_root, "item", name="ArchiveVersion", type_name="gh_version", type_code="80")
    ET.SubElement(av, "Major").text = "0"; ET.SubElement(av, "Minor").text = "2"; ET.SubElement(av, "Revision").text = "2"

    chunks_root = ET.SubElement(root, "chunks", count="1")
    defn = ET.SubElement(chunks_root, "chunk", name="Definition")
    defn_items = ET.SubElement(defn, "items", count="1")
    pv = ET.SubElement(defn_items, "item", name="plugin_version", type_name="gh_version", type_code="80")
    ET.SubElement(pv, "Major").text = "0"; ET.SubElement(pv, "Minor").text = "9"; ET.SubElement(pv, "Revision").text = "76"

    # 4 sub-chunks: DocumentHeader, DefinitionProperties, GHALibraries, DefinitionObjects
    defn_chunks = ET.SubElement(defn, "chunks", count="4")

    def ai(parent, **kw): return ET.SubElement(parent, "item", **kw)

    # DocumentHeader
    dh = ET.SubElement(defn_chunks, "chunk", name="DocumentHeader")
    dh_i = ET.SubElement(dh, "items", count="3")
    ai(dh_i, name="DocumentID",      type_name="gh_guid",   type_code="9").text  = ng()
    ai(dh_i, name="Preview",         type_name="gh_string", type_code="10").text = "Shaded"
    ai(dh_i, name="PreviewMeshType", type_name="gh_int32",  type_code="3").text  = "1"

    # DefinitionProperties
    dp = ET.SubElement(defn_chunks, "chunk", name="DefinitionProperties")
    dp_i = ET.SubElement(dp, "items", count="2")
    ai(dp_i, name="Date",        type_name="gh_date",   type_code="8").text  = "638700000000000000"
    ai(dp_i, name="Description", type_name="gh_string", type_code="10").text = "Minimal test"
    dp_c = ET.SubElement(dp, "chunks", count="1")
    ai(ET.SubElement(ET.SubElement(dp_c, "chunk", {"name": "Revisions"}), "items", {"count": "1"}),
       name="RevisionCount", type_name="gh_int32", type_code="3").text = "0"

    # GHALibraries (none needed)
    ghal = ET.SubElement(defn_chunks, "chunk", name="GHALibraries")
    ai(ET.SubElement(ghal, "items", {"count": "1"}),
       name="Count", type_name="gh_int32", type_code="3").text = "0"

    # DefinitionObjects
    dobj = ET.SubElement(defn_chunks, "chunk", name="DefinitionObjects")
    ai(ET.SubElement(dobj, "items", {"count": "1"}),
       name="ObjectCount", type_name="gh_int32", type_code="3").text = str(len(objects))
    doc_c = ET.SubElement(dobj, "chunks", count=str(len(objects)))
    for i, obj in enumerate(objects):
        obj.index = i; doc_c.append(obj.to_element())
    return root


def save(fname, objects):
    root = build_ghx(objects)
    raw  = ET.tostring(root, encoding="unicode")
    xml  = parseString(raw).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    xml  = xml.replace('<?xml version="1.0" encoding="utf-8"?>',
                       '<?xml version="1.0" encoding="utf-8" standalone="yes"?>')
    path = f"/home/user/Feet-in-Focus/{fname}"
    with open(path, "w", encoding="utf-8") as f: f.write(xml)
    print(f"✓ {fname}")


if __name__ == "__main__":
    print("Generating minimal test GHX files…\n")

    sl_obj, sl_inst = make_slider()
    pan_obj, _      = make_panel()
    py_obj, _, _, _ = make_python()
    py_wired, py_inst, _, _ = make_python(src_guid=sl_inst)
    grp_obj, _      = make_group([sl_inst, py_inst])

    save("test_slider.ghx",         [sl_obj])
    save("test_panel.ghx",          [pan_obj])
    save("test_python.ghx",         [py_obj])
    save("test_slider_python.ghx",  [sl_obj, py_wired])

    sl2, sl2_inst = make_slider()
    grp2, _ = make_group([sl2_inst])
    save("test_group.ghx",          [sl2, grp2])

    print("\nTest sequence:")
    print("  1. test_slider.ghx        — if this crashes: Slider format wrong")
    print("  2. test_panel.ghx         — if this crashes: Panel format wrong")
    print("  3. test_group.ghx         — if this crashes: Group format wrong")
    print("  4. test_python.ghx        — if this crashes: GHPython format wrong")
    print("  5. test_slider_python.ghx — if #4 works but this crashes: wire/source format wrong")
    print()
    print("Also: when the error dialog appears in Rhino, look for a Details or")
    print("'Show error details' button — that gives the full .NET stack trace.")
    print()
    print("Stack trace location: %AppData%\\McNeel\\Rhinoceros\\8.0\\logs\\")
