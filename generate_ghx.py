#!/usr/bin/env python3
"""
Grasshopper Orthotic Insole Toolkit — .ghx Generator  (v2)
Generates a complete Grasshopper XML definition file with 8 orthotic design tools.

Uses the confirmed GH_IO.dll XML format:
  - <items count="N"> and <chunks count="N"> wrappers at every level
  - Bounds/Pivot stored as <X><Y><W><H> child elements (type_code 35/31)
  - Color stored as <ARGB>A;R;G;B</ARGB> (type_code 36)
  - GHPython uses param_input/param_output/param chunk names

Confirmed GUIDs:
  Slider  : 57da07bd-ecab-415d-9d86-af36d7073abc
  Panel   : 59e0b89a-e487-49f8-bab8-b5bab16be14c  ← confirmed from real .ghx
  Group   : c552a431-af5b-46a9-a8a4-0fcbc27ef596
  GHPython: 410755b1-224a-4c1e-a407-bf32fb45ea7e

Run:    python3 generate_ghx.py
Output: Orthotic_Insole_Toolkit.ghx
"""

import uuid
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

# ── Component type GUIDs ──────────────────────────────────────────────────────
GUID_SLIDER   = "57da07bd-ecab-415d-9d86-af36d7073abc"
GUID_PANEL    = "59e0b89a-e487-49f8-bab8-b5bab16be14c"
GUID_GHPYTHON = "410755b1-224a-4c1e-a407-bf32fb45ea7e"
GUID_GROUP    = "c552a431-af5b-46a9-a8a4-0fcbc27ef596"

def ng():
    return str(uuid.uuid4()).lower()

# ── Low-level XML builders ────────────────────────────────────────────────────
class Chunk:
    """Represents a GH_IO chunk: collects items and sub-chunks, then serialises."""
    def __init__(self, name, index=None):
        self.name   = name
        self.index  = index
        self.items  = []   # (name, type_name, type_code, value_el_or_text, index)
        self.chunks = []   # Chunk objects

    def add_item(self, name, type_name, type_code, value, index=None):
        self.items.append((name, type_name, str(type_code), value, index))
        return self

    def add_chunk(self, chunk):
        self.chunks.append(chunk)
        return chunk

    # convenience helpers
    def str_(self, name, val, index=None):
        return self.add_item(name, "gh_string",          "10", str(val), index)
    def guid_(self, name, val, index=None):
        return self.add_item(name, "gh_guid",             "9",  str(val), index)
    def bool_(self, name, val):
        return self.add_item(name, "gh_bool",             "1",  "true" if val else "false")
    def int_(self, name, val, index=None):
        return self.add_item(name, "gh_int32",            "3",  str(val), index)
    def dbl_(self, name, val):
        return self.add_item(name, "gh_double",            "6",  str(val))
    def color_(self, name, a, r, g, b):
        return self.add_item(name, "gh_drawing_color", "36", ("ARGB", f"{a};{r};{g};{b}"))
    def rect_(self, name, x, y, w, h):
        return self.add_item(name, "gh_drawing_rectanglef", "35", ("XYWH", x, y, w, h))
    def pt_(self, name, x, y):
        return self.add_item(name, "gh_drawing_pointf", "31", ("XY", x, y))

    def to_element(self):
        attrs = {"name": self.name}
        if self.index is not None:
            attrs["index"] = str(self.index)
        el = ET.Element("chunk", attrs)

        if self.items:
            items_el = ET.SubElement(el, "items", {"count": str(len(self.items))})
            for (iname, itype, icode, ival, iidx) in self.items:
                ia = {"name": iname, "type_name": itype, "type_code": icode}
                if iidx is not None:
                    ia["index"] = str(iidx)
                ie = ET.SubElement(items_el, "item", ia)
                if isinstance(ival, tuple):
                    tag = ival[0]
                    if tag == "ARGB":
                        c = ET.SubElement(ie, "ARGB")
                        c.text = ival[1]
                    elif tag == "XYWH":
                        for attr, v in zip(("X","Y","W","H"), ival[1:]):
                            s = ET.SubElement(ie, attr)
                            s.text = str(int(v))
                    elif tag == "XY":
                        for attr, v in zip(("X","Y"), ival[1:]):
                            s = ET.SubElement(ie, attr)
                            s.text = str(int(v))
                else:
                    ie.text = str(ival)

        if self.chunks:
            chunks_el = ET.SubElement(el, "chunks", {"count": str(len(self.chunks))})
            for ch in self.chunks:
                chunks_el.append(ch.to_element())

        return el


# ── Component builders ────────────────────────────────────────────────────────

def make_attributes(x, y, w, h):
    """Canvas position attributes chunk."""
    ch = Chunk("Attributes")
    ch.rect_("Bounds", x, y, w, h)
    ch.pt_("Pivot", x + w//2, y + h//2)
    return ch


def make_slider(x, y, nickname, min_v, max_v, value, digits=1):
    """
    Number Slider component.
    Returns (Chunk, instance_guid).
    Wire source GUID = instance_guid (slider IS the output param).
    Uses confirmed GH 1.0.8 / Rhino 8 format (Slider sub-chunk, Optional field).
    """
    inst = ng()
    w, h = 160, 20

    obj = Chunk("Object")
    obj.guid_("GUID", GUID_SLIDER)
    obj.str_("Name", "Number Slider")

    cont = Chunk("Container")
    cont.str_("Description",   "Numeric slider for single values")
    cont.guid_("InstanceGuid", inst)
    cont.str_("Name",          "Number Slider")
    cont.str_("NickName",      nickname)
    cont.bool_("Optional",     False)
    cont.int_("SourceCount",   0)
    cont.add_chunk(make_attributes(x, y, w, h))

    sldr = cont.add_chunk(Chunk("Slider"))
    sldr.int_("Digits",      digits)
    sldr.int_("GripDisplay", 1)
    sldr.int_("Interval",    0)
    sldr.dbl_("Max",         max_v)
    sldr.dbl_("Min",         min_v)
    sldr.int_("SnapCount",   0)
    sldr.dbl_("Value",       value)

    obj.add_chunk(cont)
    return obj, inst


def make_panel(x, y, w, h, text, nickname="Panel"):
    """Panel component. Returns (Chunk, instance_guid)."""
    inst = ng()

    obj = Chunk("Object")
    obj.guid_("GUID", GUID_PANEL)
    obj.str_("Name", "Panel")

    cont = Chunk("Container")
    cont.str_("Description",   "A panel for displaying data.")
    cont.guid_("InstanceGuid", inst)
    cont.bool_("Locked",       False)
    cont.str_("Name",          "Panel")
    cont.str_("NickName",      nickname)
    cont.int_("SourceCount",   0)
    cont.str_("UserText",      text)
    cont.bool_("WrapText",     True)
    cont.add_chunk(make_attributes(x, y, w, h))
    obj.add_chunk(cont)
    return obj, inst


def make_python(x, y, w, h, name, nickname, description, inputs, outputs, code,
                sources=None):
    """
    GHPython (IronPython 2 / legacy) script component.

    inputs  : list of dict  {name, nick, desc, optional=True}
    outputs : list of dict  {name, nick, desc}
    sources : dict  {input_index: [source_guid, ...]}

    Returns (Chunk, comp_inst_guid, out_guids_dict, in_guids_dict)
    """
    if sources is None:
        sources = {}

    comp_inst = ng()
    in_guids  = {inp["name"]: ng() for inp in inputs}
    out_guids = {out["name"]: ng() for out in outputs}

    obj = Chunk("Object")
    obj.guid_("GUID", GUID_GHPYTHON)
    obj.str_("Name", "Python Script")

    cont = Chunk("Container")
    cont.str_("CodeInput",      code)
    cont.str_("Description",    description)
    cont.bool_("HideCodeInput", True)
    cont.bool_("HideOutput",    True)
    cont.guid_("InstanceGuid",  comp_inst)
    cont.bool_("IsAdvancedMode", False)
    cont.bool_("Locked",        False)
    cont.bool_("MarshalOutGuids", False)
    cont.str_("Name",           name)
    cont.str_("NickName",       nickname)

    # ── param_input ────────────────────────────────────────────────────────
    # TypeHintID "no hint" = 35915213-5534-4277-81b8-1bdc9e7383d2
    NO_HINT = "35915213-5534-4277-81b8-1bdc9e7383d2"
    pi = Chunk("param_input")
    pi.int_("param_count", len(inputs))
    for i, inp in enumerate(inputs):
        p = Chunk("param", index=i)
        p.str_("Description",  inp.get("desc", ""))
        p.guid_("InstanceGuid", in_guids[inp["name"]])
        p.str_("Name",         inp["name"])
        p.str_("NickName",     inp.get("nick", inp["name"][:6]))
        p.bool_("Optional",    inp.get("optional", True))
        p.int_("Access",       0)          # 0=item, 1=list, 2=tree
        srcs = sources.get(i, [])
        p.int_("SourceCount", len(srcs))
        for si, sg in enumerate(srcs):
            p.guid_("Source", sg, index=si)
        # TypeHint sub-chunk — GHPython always reads this
        th = Chunk("TypeHint")
        th.guid_("TypeHintID", NO_HINT)
        p.add_chunk(th)
        pi.add_chunk(p)
    cont.add_chunk(pi)

    # ── param_output ───────────────────────────────────────────────────────
    po = Chunk("param_output")
    po.int_("param_count", len(outputs))
    for i, out in enumerate(outputs):
        p = Chunk("param", index=i)
        p.str_("Description",  out.get("desc", ""))
        p.guid_("InstanceGuid", out_guids[out["name"]])
        p.str_("Name",         out["name"])
        p.str_("NickName",     out.get("nick", out["name"][:6]))
        p.bool_("Optional",    False)
        p.int_("SourceCount",  0)
        po.add_chunk(p)          # ← fixed: add to po, not cont
    cont.add_chunk(po)           # ← add po to cont

    cont.add_chunk(make_attributes(x, y, w, h))
    obj.add_chunk(cont)
    return obj, comp_inst, out_guids, in_guids


def make_group(name, member_guids, x, y, w, h, a=150, r=130, g=180, b=220):
    """Group component. Returns Chunk."""
    obj = Chunk("Object")
    obj.guid_("GUID", GUID_GROUP)
    obj.str_("Name", "Group")

    cont = Chunk("Container")
    cont.int_("Border",      1)
    cont.color_("Colour",    a, r, g, b)
    cont.str_("Description", "A group of Grasshopper objects")
    for i, mg in enumerate(member_guids):
        cont.guid_("ID", mg, index=i)
    cont.int_("ID_Count",    len(member_guids))
    cont.guid_("InstanceGuid", ng())
    cont.str_("Name",        name)
    cont.str_("NickName",    name)
    cont.add_chunk(Chunk("Attributes"))   # empty – GH auto-sizes groups
    obj.add_chunk(cont)
    return obj


# ═══════════════════════════════════════════════════════════════════════════════
# Python code for each tool
# ═══════════════════════════════════════════════════════════════════════════════

CODE_FOOT_SCAN = r"""
import Rhino.Geometry as rg
import System, System.IO
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 – Foot Scan Import & Plantar Surface Extraction
# Inputs : file_path (string), scan_mesh (Mesh - connect Geometry Pipeline)
# Outputs: foot_mesh, plantar_mesh, flat_curve, mesh_info
# ─────────────────────────────────────────────────────────────────────────────
foot_mesh    = None
plantar_mesh = None
flat_curve   = None
mesh_info    = "Connect mesh or set file_path to STL/OBJ."

try:
    m = scan_mesh
    if m is None and file_path:
        p = str(file_path)
        if System.IO.File.Exists(p):
            import Rhino
            doc = Rhino.RhinoDoc.ActiveDoc
            before = doc.Objects.Count
            doc.Import(p)
            found = []
            for i in range(before, doc.Objects.Count):
                geo = doc.Objects[i].Geometry
                if isinstance(geo, rg.Mesh):
                    found.append(geo)
            if found:
                combined = rg.Mesh()
                for mx in found: combined.Append(mx)
                m = combined

    if m is not None:
        foot_mesh = m
        m.FaceNormals.ComputeFaceNormals()
        m.Normals.ComputeNormals()

        # Extract plantar faces (normal.Z < -0.15 = pointing downward)
        plantar = rg.Mesh()
        vmap = {}
        for fi in range(m.Faces.Count):
            if m.FaceNormals[fi].Z < -0.15:
                face = m.Faces[fi]
                vis = [face.A, face.B, face.C] + ([] if face.IsTriangle else [face.D])
                nv = []
                for vi in vis:
                    if vi not in vmap:
                        vmap[vi] = plantar.Vertices.Count
                        plantar.Vertices.Add(m.Vertices[vi])
                    nv.append(vmap[vi])
                plantar.Faces.AddFace(*nv) if len(nv)==3 else plantar.Faces.AddFace(*nv)

        # Fallback: lowest 6 mm band
        if plantar.Faces.Count == 0:
            bb2 = m.GetBoundingBox(True); z_low = bb2.Min.Z; vmap2 = {}
            for fi in range(m.Faces.Count):
                face = m.Faces[fi]
                vis = [face.A, face.B, face.C] + ([] if face.IsTriangle else [face.D])
                if sum(1 for vi in vis if m.Vertices[vi].Z < z_low+6) >= 3:
                    nv = []
                    for vi in vis:
                        if vi not in vmap2:
                            vmap2[vi] = plantar.Vertices.Count
                            plantar.Vertices.Add(m.Vertices[vi])
                        nv.append(vmap2[vi])
                    plantar.Faces.AddFace(*nv) if len(nv)==3 else plantar.Faces.AddFace(*nv)

        if plantar.Faces.Count > 0:
            plantar.Compact(); plantar.Normals.ComputeNormals(); plantar.UnifyNormals()
            plantar_mesh = plantar
            flat = rg.Mesh()
            for v in plantar.Vertices: flat.Vertices.Add(rg.Point3d(v.X, v.Y, 0.0))
            for fi in range(plantar.Faces.Count):
                f = plantar.Faces[fi]
                flat.Faces.AddFace(f.A,f.B,f.C) if f.IsTriangle else flat.Faces.AddFace(f.A,f.B,f.C,f.D)
            flat.Normals.ComputeNormals(); flat.UnifyNormals()
            edges = flat.GetNakedEdges()
            if edges: flat_curve = max(edges, key=lambda c: c.GetLength())

        bb = m.GetBoundingBox(True)
        mesh_info = ("Foot Scan Loaded\nLength:{:.1f}mm Width:{:.1f}mm Height:{:.1f}mm\nFaces:{:d}".format(
            bb.Max.Y-bb.Min.Y, bb.Max.X-bb.Min.X, bb.Max.Z-bb.Min.Z, m.Faces.Count))
except Exception as _e:
    mesh_info = "Error: " + str(_e)
"""

CODE_INSOLE_OUTLINE = r"""
import Rhino.Geometry as rg
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 – Insole Outline Generator
# Inputs : flat_curve (Curve from 01), offset_mm (number), smoothing (0-1)
# Outputs: insole_outline, heel_pt, toe_pt, insole_length, insole_width
# ─────────────────────────────────────────────────────────────────────────────
insole_outline = None; heel_pt = None; toe_pt = None
insole_length  = 0.0;  insole_width = 0.0

try:
    if flat_curve is not None:
        crv = flat_curve
        od  = float(offset_mm)  if offset_mm  is not None else -2.0
        sm  = float(smoothing)  if smoothing  is not None else 0.3
        if od > 0: od = -od
        offs = crv.Offset(rg.Plane.WorldXY, od, 0.1, rg.CurveOffsetCornerStyle.Round)
        result = offs[0] if offs else crv
        if sm > 0.05:
            n  = max(24, int(60*sm)); dom = result.Domain
            pts = [result.PointAt(dom.ParameterAt(i/float(n))) for i in range(n+1)]
            f   = rg.Curve.CreateInterpolatedCurve(pts, 3)
            if f: result = f
        insole_outline = result
        bb = result.GetBoundingBox(True)
        cx = (bb.Min.X+bb.Max.X)/2.0
        insole_length = round(bb.Max.Y-bb.Min.Y, 2)
        insole_width  = round(bb.Max.X-bb.Min.X, 2)
        heel_pt = rg.Point3d(cx, bb.Min.Y, 0.0)
        toe_pt  = rg.Point3d(cx, bb.Max.Y, 0.0)
except Exception as _e:
    print("Outline error: "+str(_e))
"""

CODE_ARCH = r"""
import Rhino.Geometry as rg, math
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 – Medial Arch Height Mapper
# Inputs : insole_outline, arch_height (mm), arch_peak (0-1), arch_width (mm), foot_side (R/L)
# Outputs: arch_surface, arch_spine, arch_profiles
# ─────────────────────────────────────────────────────────────────────────────
arch_surface = None; arch_spine = None; arch_profiles = []
try:
    if insole_outline is not None:
        bb   = insole_outline.GetBoundingBox(True)
        flen = bb.Max.Y - bb.Min.Y; fwid = bb.Max.X - bb.Min.X
        ah   = float(arch_height) if arch_height is not None else 15.0
        ap   = float(arch_peak)   if arch_peak   is not None else 0.35
        aw   = float(arch_width)  if arch_width  is not None else 30.0
        side = str(foot_side).strip().upper() if foot_side else "R"
        med_x = bb.Min.X + fwid*0.12 if side=="R" else bb.Max.X - fwid*0.12
        y0 = bb.Min.Y+0.10*flen; y_pk = bb.Min.Y+ap*flen; y1 = bb.Min.Y+0.72*flen
        N  = 30; spine_pts = []
        for i in range(N+1):
            t    = i/float(N); y = y0+t*(y1-y0)
            t_pk = (y_pk-y0)/(y1-y0) if (y1-y0)>0 else 0.35
            z    = max(0.0, ah*math.exp(-((t-t_pk)**2)/0.06))
            spine_pts.append(rg.Point3d(med_x, y, z))
        arch_spine = rg.Curve.CreateInterpolatedCurve(spine_pts, 3)
        profs = []
        for i in range(N+1):
            t    = i/float(N); y = y0+t*(y1-y0)
            t_pk = (y_pk-y0)/(y1-y0) if (y1-y0)>0 else 0.35
            z    = max(0.0, ah*math.exp(-((t-t_pk)**2)/0.06))
            if z < 0.3: continue
            lw   = max(6.0, aw*(1.0-0.5*abs(t-t_pk)/max(t_pk,1-t_pk)))
            apl  = rg.Plane(rg.Point3d(med_x,y,0.0), rg.Vector3d.XAxis, rg.Vector3d.ZAxis)
            arc  = rg.Arc(apl, lw, math.pi).ToNurbsCurve()
            xf   = rg.Transform.Scale(rg.Plane(rg.Point3d(med_x,y,0.0),
                       rg.Vector3d.XAxis, rg.Vector3d.ZAxis), 1.0, 1.0, z/lw)
            arc.Transform(xf); profs.append(arc)
        arch_profiles = profs
        if len(profs)>=2:
            b = rg.Brep.CreateFromLoft(profs, rg.Point3d.Unset, rg.Point3d.Unset,
                                       rg.LoftType.Normal, False)
            if b: arch_surface = b[0]
except Exception as _e:
    print("Arch error: "+str(_e))
"""

CODE_HEEL_CUP = r"""
import Rhino.Geometry as rg, math
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 – Heel Cup Designer
# Inputs : insole_outline, cup_depth (mm), cup_angle (deg), cup_width_pct (0-1)
# Outputs: heel_cup_surface, heel_cup_info
# ─────────────────────────────────────────────────────────────────────────────
heel_cup_surface = None; heel_cup_info = ""
try:
    if insole_outline is not None:
        bb   = insole_outline.GetBoundingBox(True)
        flen = bb.Max.Y-bb.Min.Y; fwid = bb.Max.X-bb.Min.X
        cx   = (bb.Min.X+bb.Max.X)/2.0
        cd   = float(cup_depth)     if cup_depth     is not None else 12.0
        ca   = float(cup_angle)     if cup_angle     is not None else 15.0
        cwp  = float(cup_width_pct) if cup_width_pct is not None else 0.75
        half_w = fwid*cwp/2.0; heel_y = bb.Min.Y; heel_ey = bb.Min.Y+flen*0.28
        profs = []
        for i in range(13):
            t  = i/12.0; y = heel_y+t*(heel_ey-heel_y)
            r  = half_w*math.sqrt(max(0.0,1.0-t**2))
            if r<2.0: continue
            zw = max(0.0, cd*math.cos(math.radians(ca))*(1.0-0.4*t))
            base = rg.Point3d(cx,y,0.0)
            arc  = rg.Arc(rg.Plane(base,rg.Vector3d.XAxis,rg.Vector3d.ZAxis),r,math.pi).ToNurbsCurve()
            if r>0:
                xf = rg.Transform.Scale(rg.Plane(base,rg.Vector3d.XAxis,rg.Vector3d.ZAxis),
                                        1.0,1.0,zw/r)
                arc.Transform(xf); profs.append(arc)
        if len(profs)>=2:
            b = rg.Brep.CreateFromLoft(profs,rg.Point3d.Unset,rg.Point3d.Unset,
                                       rg.LoftType.Normal,False)
            if b: heel_cup_surface = b[0]
        heel_cup_info = "Heel Cup\nDepth:{:.1f}mm Angle:{:.1f}deg Width:{:.1f}mm".format(cd,ca,half_w*2)
except Exception as _e:
    heel_cup_info = "Error: "+str(_e)
"""

CODE_METATARSAL = r"""
import Rhino.Geometry as rg, math
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 – Metatarsal Dome
# Inputs : insole_outline, dome_height (mm), dome_x_pct (0-1), dome_y_pct (0-1), dome_radius (mm)
# Outputs: dome_surface, dome_centre
# ─────────────────────────────────────────────────────────────────────────────
dome_surface = None; dome_centre = None
try:
    if insole_outline is not None:
        bb   = insole_outline.GetBoundingBox(True)
        flen = bb.Max.Y-bb.Min.Y; fwid = bb.Max.X-bb.Min.X
        dh   = float(dome_height) if dome_height  is not None else 6.0
        dxp  = float(dome_x_pct)  if dome_x_pct   is not None else 0.5
        dyp  = float(dome_y_pct)  if dome_y_pct   is not None else 0.63
        dr   = float(dome_radius) if dome_radius   is not None else 20.0
        cx   = bb.Min.X+dxp*fwid; cy = bb.Min.Y+dyp*flen
        dome_centre = rg.Point3d(cx,cy,0.0)
        N = 20; prof_pts = []
        for i in range(N+1):
            t = i/float(N)
            prof_pts.append(rg.Point3d(cx+dr*math.sin(t*math.pi), cy, dh*math.sin(t*math.pi)))
        pc = rg.Curve.CreateInterpolatedCurve(prof_pts,3)
        if pc:
            rev = rg.RevSurface.Create(pc, rg.Line(rg.Point3d(cx,cy,0),rg.Point3d(cx,cy,dh)),
                                       0, 2*math.pi)
            if rev: dome_surface = rev.ToBrep()
except Exception as _e:
    print("Dome error: "+str(_e))
"""

CODE_POSTING = r"""
import Rhino.Geometry as rg, math
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6 – Posting / Wedging
# Inputs : insole_outline, rf_med_deg, rf_lat_deg, ff_med_deg, ff_lat_deg
# Outputs: rf_post_brep, ff_post_brep, posting_info
# ─────────────────────────────────────────────────────────────────────────────
rf_post_brep = None; ff_post_brep = None; posting_info = ""
try:
    if insole_outline is not None:
        bb   = insole_outline.GetBoundingBox(True)
        flen = bb.Max.Y-bb.Min.Y; fwid = bb.Max.X-bb.Min.X
        rmd  = float(rf_med_deg) if rf_med_deg is not None else 0.0
        rld  = float(rf_lat_deg) if rf_lat_deg is not None else 0.0
        fmd  = float(ff_med_deg) if ff_med_deg is not None else 0.0
        fld  = float(ff_lat_deg) if ff_lat_deg is not None else 0.0

        def wedge(y1, y2, med_d, lat_d):
            cx2  = (bb.Min.X+bb.Max.X)/2.0
            mh   = fwid/2.0*math.tan(math.radians(abs(med_d)))
            lh   = fwid/2.0*math.tan(math.radians(abs(lat_d)))
            def bz(x):
                rel = (x-cx2)/(fwid/2.0) if fwid>0 else 0
                return -abs(mh)*abs(rel) if rel<0 else -abs(lh)*abs(rel)
            tr = rg.PolylineCurve([rg.Point3d(bb.Min.X,y1,0),rg.Point3d(bb.Max.X,y1,0),
                                   rg.Point3d(bb.Max.X,y2,0),rg.Point3d(bb.Min.X,y2,0),rg.Point3d(bb.Min.X,y1,0)])
            br = rg.PolylineCurve([rg.Point3d(bb.Min.X,y1,bz(bb.Min.X)),rg.Point3d(bb.Max.X,y1,bz(bb.Max.X)),
                                   rg.Point3d(bb.Max.X,y2,bz(bb.Max.X)),rg.Point3d(bb.Min.X,y2,bz(bb.Min.X)),
                                   rg.Point3d(bb.Min.X,y1,bz(bb.Min.X))])
            ls = rg.Brep.CreateFromLoft([tr,br],rg.Point3d.Unset,rg.Point3d.Unset,rg.LoftType.Straight,False)
            return ls[0] if ls else None

        if abs(rmd)>0.01 or abs(rld)>0.01:
            rf_post_brep = wedge(bb.Min.Y, bb.Min.Y+0.35*flen, rmd, rld)
        if abs(fmd)>0.01 or abs(fld)>0.01:
            ff_post_brep = wedge(bb.Min.Y+0.65*flen, bb.Max.Y, fmd, fld)
        posting_info = "Posting\nRF Med:{:.1f} Lat:{:.1f}\nFF Med:{:.1f} Lat:{:.1f}".format(rmd,rld,fmd,fld)
except Exception as _e:
    posting_info = "Error: "+str(_e)
"""

CODE_ASSEMBLY = r"""
import Rhino.Geometry as rg
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 7 – Insole Assembly & Thickness Control
# Inputs : insole_outline, arch_surface, heel_cup_surface, dome_surface,
#          rf_post_brep, ff_post_brep, top_cover_mm, shell_mm, base_mm
# Outputs: insole_shell, insole_solid, assembly_info
# ─────────────────────────────────────────────────────────────────────────────
insole_shell = None; insole_solid = None; assembly_info = ""
try:
    if insole_outline is not None:
        bb   = insole_outline.GetBoundingBox(True)
        flen = bb.Max.Y-bb.Min.Y; fwid = bb.Max.X-bb.Min.X
        tc   = float(top_cover_mm) if top_cover_mm is not None else 1.5
        sh   = float(shell_mm)     if shell_mm     is not None else 4.0
        ba   = float(base_mm)      if base_mm      is not None else 2.0
        total = tc+sh+ba

        crv = insole_outline
        if not crv.IsClosed: crv = crv.ToNurbsCurve()
        caps = rg.Brep.CreatePlanarBreps([crv], 0.01)
        if caps:
            extruded = []
            for cap in caps:
                ex = cap.Faces[0].CreateExtrusion(rg.Vector3d(0,0,-total), True)
                if ex: extruded.append(ex)
            if extruded:
                insole_shell = extruded[0]
                parts = [insole_shell]
                for g in [arch_surface, heel_cup_surface, dome_surface, rf_post_brep, ff_post_brep]:
                    if g is not None: parts.append(g)
                if len(parts)>1:
                    j = rg.Brep.JoinBreps(parts, 0.1)
                    insole_solid = j[0] if j else insole_shell
                else:
                    insole_solid = insole_shell
        assembly_info = ("Assembly\nTop:{:.1f} Shell:{:.1f} Base:{:.1f} Total:{:.1f}mm\n"
                         "Footprint:{:.0f}x{:.0f}mm".format(tc,sh,ba,total,flen,fwid))
except Exception as _e:
    assembly_info = "Error: "+str(_e)
"""

CODE_EXPORT = r"""
import Rhino.Geometry as rg, math
# ─────────────────────────────────────────────────────────────────────────────
# TOOL 8 – Export-Ready Brep + 2D Rocker-Bottom Outline
# Inputs : insole_solid, insole_outline, rocker_angle (deg), rocker_apex_pct (0-1)
# Outputs: export_brep, rocker_outline, rocker_profile, export_info
# ─────────────────────────────────────────────────────────────────────────────
export_brep = None; rocker_outline = None; rocker_profile = None
export_info = "Connect 07 Assembly output."
try:
    if insole_solid is not None:
        rep = insole_solid.DuplicateBrep()
        rep.MergeCoplanarFaces(0.01)
        export_brep = rep
        export_info = "Export brep ready  Faces:{:d}".format(rep.Faces.Count)

    if insole_outline is not None:
        bb   = insole_outline.GetBoundingBox(True)
        flen = bb.Max.Y-bb.Min.Y; cx = (bb.Min.X+bb.Max.X)/2.0
        ra   = float(rocker_angle)    if rocker_angle    is not None else 10.0
        rap  = float(rocker_apex_pct) if rocker_apex_pct is not None else 0.50
        apex = bb.Min.Y+rap*flen; tan_ = math.tan(math.radians(ra))

        # Side-view rocker profile
        prof = [rg.Point3d(cx, bb.Min.Y+i/60.0*flen,
                max(0.0,-(bb.Min.Y+i/60.0*flen-apex))*tan_*-1) for i in range(61)]
        rocker_profile = rg.Curve.CreateInterpolatedCurve(prof, 3)

        # 2-D rocker contact outline projected onto rocker plane
        n  = rg.NurbsCurve = insole_outline.ToNurbsCurve()
        dom = n.Domain; pts2 = []
        for i in range(101):
            pt = n.PointAt(dom.ParameterAt(i/100.0))
            z  = -(pt.Y-apex)*tan_ if pt.Y>apex else 0.0
            pts2.append(rg.Point3d(pt.X, pt.Y, z))
        pts2.append(pts2[0])
        rocker_outline = rg.Curve.CreateInterpolatedCurve(pts2, 3)
except Exception as _e:
    export_info = "Error: "+str(_e)
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Main builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_document():
    """Build the complete GHX document as a list of Chunk objects + metadata."""

    all_objects = []   # list of Chunk objects (the canvas objects)
    sl_guids    = {}   # logical_key → slider_instance_guid
    comp_outs   = {}   # logical_key → {output_name: output_param_guid}
    comp_insts  = {}   # logical_key → comp_instance_guid
    group_members = {} # group_name → [instance_guids]

    # ── helpers ───────────────────────────────────────────────────────────────
    def sl(key, x, y, nick, mn, mx, val, dg=1):
        obj, inst = make_slider(x, y, nick, mn, mx, val, dg)
        all_objects.append(obj)
        sl_guids[key] = inst
        return inst

    def py(key, x, y, w, h, name, nick, desc, inputs, outputs, code, sources=None):
        obj, inst, out_g, in_g = make_python(x, y, w, h, name, nick, desc,
                                              inputs, outputs, code, sources)
        all_objects.append(obj)
        comp_outs[key]  = out_g
        comp_insts[key] = inst
        return inst, out_g, in_g

    def pan(x, y, w, h, text, nick="Note"):
        obj, inst = make_panel(x, y, w, h, text, nick)
        all_objects.append(obj)
        return inst

    def grp(name, members, x, y, w, h, a=150, r=130, g=160, b=220):
        obj = make_group(name, members, x, y, w, h, a, r, g, b)
        all_objects.append(obj)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 1 – Foot Scan Import  (x ≈ 30)
    # ──────────────────────────────────────────────────────────────────────────
    C1 = 30
    pan(C1, 20, 380, 55,
        "ORTHOTIC INSOLE TOOLKIT\n"
        "8-tool parametric insole design for CNC/EVA milling & 3D printing.", "Title")

    pan(C1, 85, 380, 180,
        "SETUP:\n"
        "1. Import your foot scan STL into Rhino\n"
        "2. Use Geometry Pipeline to connect the mesh\n"
        "   to the scan_mesh input of component 01.\n"
        "3. Adjust sliders for each tool.\n"
        "4. Tools flow left → right (01 → 08).\n"
        "5. Right-click any output → Bake to add to Rhino.", "Instructions")

    s1_scan = sl("scan_mesh_path", C1, 276, "file_path (optional)", 0, 0, 0, 0)
    SCAN_INPUTS = [
        {"name":"file_path", "nick":"fp",   "desc":"Path to STL/OBJ foot scan (optional)"},
        {"name":"scan_mesh", "nick":"mesh", "desc":"Direct mesh connection (preferred - use Geometry Pipeline)"},
    ]
    SCAN_OUTPUTS = [
        {"name":"foot_mesh",    "nick":"Mesh",  "desc":"Full foot mesh"},
        {"name":"plantar_mesh", "nick":"Plan",  "desc":"Plantar surface mesh"},
        {"name":"flat_curve",   "nick":"FlatC", "desc":"2D plantar boundary at Z=0"},
        {"name":"mesh_info",    "nick":"Info",  "desc":"Foot dimensions"},
    ]
    s1_inst, s1_out, s1_in = py(
        "scan", C1, 300, 200, 140,
        "01 Foot Scan Import", "01 FootScan",
        "Imports foot scan STL/OBJ and extracts plantar surface",
        SCAN_INPUTS, SCAN_OUTPUTS, CODE_FOOT_SCAN
    )
    grp("01 Foot Scan", [s1_scan, s1_inst], C1-5, 15, 240, 470, 150,100,160,220)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 2 – Insole Outline  (x ≈ 270)
    # ──────────────────────────────────────────────────────────────────────────
    C2 = 280
    pan(C2, 20, 250, 30, "INSOLE OUTLINE", "S2 Title")
    sl2_off = sl("offset_mm", C2, 60,  "Offset mm (negative=inward)", -15, 0,  -2.0, 1)
    sl2_sm  = sl("smoothing", C2, 90,  "Smoothing 0-1",                 0, 1,   0.3, 2)
    OUTLINE_INS = [
        {"name":"flat_curve",  "nick":"FlatC","desc":"Boundary curve from 01"},
        {"name":"offset_mm",   "nick":"Off",  "desc":"Inward offset in mm"},
        {"name":"smoothing",   "nick":"Sm",   "desc":"0=sharp 1=smooth"},
    ]
    OUTLINE_OUTS = [
        {"name":"insole_outline","nick":"Outl","desc":"2D insole perimeter"},
        {"name":"heel_pt",       "nick":"Heel","desc":"Heel centre point"},
        {"name":"toe_pt",        "nick":"Toe", "desc":"Toe centre point"},
        {"name":"insole_length", "nick":"Len", "desc":"Foot length mm"},
        {"name":"insole_width",  "nick":"Wid", "desc":"Foot width mm"},
    ]
    s2_src = {1:[sl2_off], 2:[sl2_sm]}
    s2_inst, s2_out, _ = py(
        "outline", C2, 120, 200, 160,
        "02 Insole Outline", "02 Outline",
        "Generates the 2D insole perimeter from foot scan boundary",
        OUTLINE_INS, OUTLINE_OUTS, CODE_INSOLE_OUTLINE, s2_src
    )
    grp("02 Insole Outline", [sl2_off, sl2_sm, s2_inst], C2-5, 15, 240, 310, 150,120,200,120)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 3 – Arch Height  (x ≈ 530)
    # ──────────────────────────────────────────────────────────────────────────
    C3 = 540
    pan(C3, 20, 250, 30, "MEDIAL ARCH", "S3 Title")
    sl3_ah  = sl("arch_height", C3,  60, "Arch Height mm (0-30)", 0, 30, 15.0, 1)
    sl3_ap  = sl("arch_peak",   C3,  90, "Arch Peak 0=heel 1=toe", 0,  1,  0.35, 2)
    sl3_aw  = sl("arch_width",  C3, 120, "Arch Width mm",         10, 60, 30.0, 1)
    ARCH_INS = [
        {"name":"insole_outline","nick":"Outl","desc":"From 02"},
        {"name":"arch_height",   "nick":"AH",  "desc":"Arch height mm"},
        {"name":"arch_peak",     "nick":"AP",  "desc":"Peak position along foot (0-1)"},
        {"name":"arch_width",    "nick":"AW",  "desc":"Arch base width mm"},
        {"name":"foot_side",     "nick":"Side","desc":"R or L for foot side"},
    ]
    ARCH_OUTS = [
        {"name":"arch_surface",  "nick":"Srf",  "desc":"3D arch brep"},
        {"name":"arch_spine",    "nick":"Spine","desc":"Height profile curve"},
        {"name":"arch_profiles", "nick":"Prof", "desc":"Cross-section arcs"},
    ]
    s3_src = {1:[sl3_ah], 2:[sl3_ap], 3:[sl3_aw]}
    s3_inst, s3_out, _ = py(
        "arch", C3, 160, 200, 170,
        "03 Medial Arch", "03 Arch",
        "Generates medial arch geometry with adjustable height and position",
        ARCH_INS, ARCH_OUTS, CODE_ARCH, s3_src
    )
    pan(C3, 342, 120, 60, "R", "foot_side")   # standalone panel for foot_side
    grp("03 Arch", [sl3_ah,sl3_ap,sl3_aw,s3_inst], C3-5,15,240,360,150,200,120,120)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 4 – Heel Cup  (x ≈ 800)
    # ──────────────────────────────────────────────────────────────────────────
    C4 = 800
    pan(C4, 20, 250, 30, "HEEL CUP", "S4 Title")
    sl4_cd  = sl("cup_depth",     C4,  60, "Cup Depth mm",      0, 25, 12.0, 1)
    sl4_ca  = sl("cup_angle",     C4,  90, "Cup Angle degrees", 0, 30, 15.0, 1)
    sl4_cw  = sl("cup_width_pct", C4, 120, "Cup Width 0-1",     0,  1,  0.75, 2)
    HEEL_INS = [
        {"name":"insole_outline", "nick":"Outl","desc":"From 02"},
        {"name":"cup_depth",      "nick":"CD",  "desc":"Cup depth mm"},
        {"name":"cup_angle",      "nick":"CA",  "desc":"Cup wall angle degrees"},
        {"name":"cup_width_pct",  "nick":"CW",  "desc":"Cup width as fraction of foot width"},
    ]
    HEEL_OUTS = [
        {"name":"heel_cup_surface","nick":"HCup","desc":"3D heel cup brep"},
        {"name":"heel_cup_info",   "nick":"Info","desc":"Cup parameters"},
    ]
    s4_src = {1:[sl4_cd], 2:[sl4_ca], 3:[sl4_cw]}
    s4_inst, s4_out, _ = py(
        "heel", C4, 160, 200, 130,
        "04 Heel Cup", "04 HeelCup",
        "Parametric heel cup with depth and angle controls",
        HEEL_INS, HEEL_OUTS, CODE_HEEL_CUP, s4_src
    )
    grp("04 Heel Cup",[sl4_cd,sl4_ca,sl4_cw,s4_inst],C4-5,15,240,330,150,220,150,80)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 5 – Metatarsal Dome  (x ≈ 1060)
    # ──────────────────────────────────────────────────────────────────────────
    C5 = 1060
    pan(C5, 20, 250, 30, "METATARSAL DOME", "S5 Title")
    sl5_dh  = sl("dome_height", C5,  60, "Dome Height mm",    0, 15,  6.0, 1)
    sl5_dx  = sl("dome_x_pct",  C5,  90, "Dome X pos 0-1",   0,  1,  0.5, 2)
    sl5_dy  = sl("dome_y_pct",  C5, 120, "Dome Y pos 0-1",   0,  1,  0.63,2)
    sl5_dr  = sl("dome_radius", C5, 150, "Dome Radius mm",   5, 40, 20.0, 1)
    DOME_INS = [
        {"name":"insole_outline","nick":"Outl","desc":"From 02"},
        {"name":"dome_height",   "nick":"DH",  "desc":"Dome height mm"},
        {"name":"dome_x_pct",    "nick":"DX",  "desc":"Medial-lateral position (0-1)"},
        {"name":"dome_y_pct",    "nick":"DY",  "desc":"Heel-toe position (0-1)"},
        {"name":"dome_radius",   "nick":"DR",  "desc":"Dome base radius mm"},
    ]
    DOME_OUTS = [
        {"name":"dome_surface","nick":"Dome","desc":"3D metatarsal dome brep"},
        {"name":"dome_centre", "nick":"DC",  "desc":"Dome centre point"},
    ]
    s5_src = {1:[sl5_dh],2:[sl5_dx],3:[sl5_dy],4:[sl5_dr]}
    s5_inst, s5_out, _ = py(
        "dome", C5, 180, 200, 170,
        "05 Metatarsal Dome", "05 MetDome",
        "Adds forefoot metatarsal support pad at adjustable position",
        DOME_INS, DOME_OUTS, CODE_METATARSAL, s5_src
    )
    grp("05 Metatarsal Dome",[sl5_dh,sl5_dx,sl5_dy,sl5_dr,s5_inst],C5-5,15,240,370,150,80,120,220)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 6 – Posting  (x ≈ 1320)
    # ──────────────────────────────────────────────────────────────────────────
    C6 = 1320
    pan(C6, 20, 250, 30, "POSTING / WEDGING", "S6 Title")
    sl6_rmd = sl("rf_med_deg", C6,  60, "RF Medial deg",  0, 10, 0.0, 1)
    sl6_rld = sl("rf_lat_deg", C6,  90, "RF Lateral deg", 0, 10, 0.0, 1)
    sl6_fmd = sl("ff_med_deg", C6, 120, "FF Medial deg",  0, 10, 0.0, 1)
    sl6_fld = sl("ff_lat_deg", C6, 150, "FF Lateral deg", 0, 10, 0.0, 1)
    POST_INS = [
        {"name":"insole_outline","nick":"Outl","desc":"From 02"},
        {"name":"rf_med_deg",    "nick":"RFM", "desc":"Rearfoot medial post degrees"},
        {"name":"rf_lat_deg",    "nick":"RFL", "desc":"Rearfoot lateral post degrees"},
        {"name":"ff_med_deg",    "nick":"FFM", "desc":"Forefoot medial post degrees"},
        {"name":"ff_lat_deg",    "nick":"FFL", "desc":"Forefoot lateral post degrees"},
    ]
    POST_OUTS = [
        {"name":"rf_post_brep", "nick":"RF",  "desc":"Rearfoot wedge brep"},
        {"name":"ff_post_brep", "nick":"FF",  "desc":"Forefoot wedge brep"},
        {"name":"posting_info", "nick":"Info","desc":"Posting summary"},
    ]
    s6_src = {1:[sl6_rmd],2:[sl6_rld],3:[sl6_fmd],4:[sl6_fld]}
    s6_inst, s6_out, _ = py(
        "post", C6, 180, 200, 170,
        "06 Posting / Wedging", "06 Posting",
        "Adds medial and lateral rearfoot and forefoot wedge angles",
        POST_INS, POST_OUTS, CODE_POSTING, s6_src
    )
    grp("06 Posting",[sl6_rmd,sl6_rld,sl6_fmd,sl6_fld,s6_inst],C6-5,15,240,370,150,200,200,80)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 7 – Assembly  (x ≈ 1580)
    # ──────────────────────────────────────────────────────────────────────────
    C7 = 1580
    pan(C7, 20, 250, 30, "INSOLE ASSEMBLY", "S7 Title")
    sl7_tc  = sl("top_cover_mm", C7,  60, "Top Cover mm",  0.5, 4,  1.5, 1)
    sl7_sh  = sl("shell_mm",     C7,  90, "Shell mm",      1,  10,  4.0, 1)
    sl7_ba  = sl("base_mm",      C7, 120, "Base mm",       1,   6,  2.0, 1)
    ASSM_INS = [
        {"name":"insole_outline",   "nick":"Outl","desc":"From 02"},
        {"name":"arch_surface",     "nick":"Arch","desc":"From 03"},
        {"name":"heel_cup_surface", "nick":"HCup","desc":"From 04"},
        {"name":"dome_surface",     "nick":"Dome","desc":"From 05"},
        {"name":"rf_post_brep",     "nick":"RFP", "desc":"From 06"},
        {"name":"ff_post_brep",     "nick":"FFP", "desc":"From 06"},
        {"name":"top_cover_mm",     "nick":"TC",  "desc":"Top cover thickness mm"},
        {"name":"shell_mm",         "nick":"Sh",  "desc":"Shell thickness mm"},
        {"name":"base_mm",          "nick":"Ba",  "desc":"Base thickness mm"},
    ]
    ASSM_OUTS = [
        {"name":"insole_shell",  "nick":"Shell","desc":"Shell brep (outline extruded)"},
        {"name":"insole_solid",  "nick":"Solid","desc":"Complete insole solid brep"},
        {"name":"assembly_info", "nick":"Info", "desc":"Layer thickness summary"},
    ]
    s7_src = {6:[sl7_tc], 7:[sl7_sh], 8:[sl7_ba]}
    s7_inst, s7_out, _ = py(
        "assm", C7, 160, 200, 280,
        "07 Insole Assembly", "07 Assembly",
        "Sets top cover, shell and base layer thicknesses and assembles solid insole",
        ASSM_INS, ASSM_OUTS, CODE_ASSEMBLY, s7_src
    )
    grp("07 Assembly",[sl7_tc,sl7_sh,sl7_ba,s7_inst],C7-5,15,240,420,150,120,200,200)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 8 – Export + Rocker  (x ≈ 1840)
    # ──────────────────────────────────────────────────────────────────────────
    C8 = 1840
    pan(C8, 20, 250, 30, "EXPORT + ROCKER", "S8 Title")
    sl8_ra  = sl("rocker_angle",    C8,  60, "Rocker Angle deg",     0, 25, 10.0, 1)
    sl8_rap = sl("rocker_apex_pct", C8,  90, "Rocker Apex 0=heel 1=toe", 0, 1, 0.5, 2)
    EXPORT_INS = [
        {"name":"insole_solid",    "nick":"Sol", "desc":"From 07 - complete insole brep"},
        {"name":"insole_outline",  "nick":"Outl","desc":"From 02 - 2D perimeter"},
        {"name":"rocker_angle",    "nick":"RA",  "desc":"Rocker bottom angle degrees"},
        {"name":"rocker_apex_pct", "nick":"RAP", "desc":"Rocker apex position (0-1)"},
    ]
    EXPORT_OUTS = [
        {"name":"export_brep",    "nick":"Brep", "desc":"Export-ready NURBS solid for CNC or 3D print"},
        {"name":"rocker_outline", "nick":"Rock", "desc":"2D rocker-bottom contact outline"},
        {"name":"rocker_profile", "nick":"Prof", "desc":"Rocker profile side-view curve"},
        {"name":"export_info",    "nick":"Info", "desc":"Export status"},
    ]
    s8_src = {2:[sl8_ra], 3:[sl8_rap]}
    s8_inst, s8_out, _ = py(
        "export", C8, 150, 200, 150,
        "08 Export + Rocker", "08 Export",
        "Outputs NURBS solid ready for CNC milling or 3D printing, plus 2D rocker outline",
        EXPORT_INS, EXPORT_OUTS, CODE_EXPORT, s8_src
    )
    pan(C8, 320, 380, 260,
        "MANUFACTURING OUTPUTS\n"
        "CNC/EVA: Right-click export_brep → Bake\n"
        "  then File > Export Selected (STL or STEP).\n"
        "3D Print: Bake insole_solid → export STL.\n"
        "Rocker 2D: Bake rocker_outline → export DXF.\n"
        "Shoe Last integration: connect last surface\n"
        "  to insole_outline input of 02.", "Export Notes")
    grp("08 Export+Rocker",[sl8_ra,sl8_rap,s8_inst],C8-5,15,240,360,150,200,80,120)

    return all_objects


# ── Assemble root XML ─────────────────────────────────────────────────────────

def build_root(objects):
    root = ET.Element("Archive", name="Root")

    # Archive version
    items_root = ET.SubElement(root, "items", count="1")
    av = ET.SubElement(items_root, "item",
                       name="ArchiveVersion", type_name="gh_version", type_code="80")
    ET.SubElement(av, "Major").text    = "0"
    ET.SubElement(av, "Minor").text    = "2"
    ET.SubElement(av, "Revision").text = "2"

    # Single Definition chunk
    chunks_root = ET.SubElement(root, "chunks", count="1")
    defn = ET.SubElement(chunks_root, "chunk", name="Definition")

    # plugin_version item
    defn_items = ET.SubElement(defn, "items", count="1")
    pv = ET.SubElement(defn_items, "item",
                       name="plugin_version", type_name="gh_version", type_code="80")
    ET.SubElement(pv, "Major").text    = "1"
    ET.SubElement(pv, "Minor").text    = "0"
    ET.SubElement(pv, "Revision").text = "8"

    # 5 definition sub-chunks (confirmed from real Rhino 8 / GH 1.0.8 GHX)
    defn_chunks = ET.SubElement(defn, "chunks", count="5")

    def add_item(parent, **kw):
        return ET.SubElement(parent, "item", **kw)

    # ── DocumentHeader (5 items — confirmed from real GHX) ───────────────────
    dh = ET.SubElement(defn_chunks, "chunk", name="DocumentHeader")
    dh_items = ET.SubElement(dh, "items", count="5")
    add_item(dh_items, name="DocumentID",      type_name="gh_guid",          type_code="9").text  = ng()
    add_item(dh_items, name="Preview",         type_name="gh_string",        type_code="10").text = "Shaded"
    add_item(dh_items, name="PreviewMeshType", type_name="gh_int32",         type_code="3").text  = "1"
    pn = add_item(dh_items, name="PreviewNormal",   type_name="gh_drawing_color", type_code="36")
    ET.SubElement(pn, "ARGB").text = "100;150;0;0"
    ps = add_item(dh_items, name="PreviewSelected", type_name="gh_drawing_color", type_code="36")
    ET.SubElement(ps, "ARGB").text = "100;0;150;0"

    # ── DefinitionProperties (4 items + 3 sub-chunks — confirmed) ────────────
    dp = ET.SubElement(defn_chunks, "chunk", name="DefinitionProperties")
    dp_items = ET.SubElement(dp, "items", count="4")
    add_item(dp_items, name="Date",        type_name="gh_date",   type_code="8").text  = "638700000000000000"
    add_item(dp_items, name="Description", type_name="gh_string", type_code="10").text = "Orthotic Insole Toolkit"
    add_item(dp_items, name="KeepOpen",    type_name="gh_bool",   type_code="1").text  = "false"
    add_item(dp_items, name="Name",        type_name="gh_string", type_code="10").text = "Orthotic_Insole_Toolkit"
    dp_chunks = ET.SubElement(dp, "chunks", count="3")
    rev = ET.SubElement(dp_chunks, "chunk", name="Revisions")
    ET.SubElement(ET.SubElement(rev, "items", count="1"), "item",
                  name="RevisionCount", type_name="gh_int32", type_code="3").text = "0"
    proj = ET.SubElement(dp_chunks, "chunk", name="Projection")
    proj_i = ET.SubElement(proj, "items", count="2")
    tgt = add_item(proj_i, name="Target", type_name="gh_drawing_point", type_code="30")
    ET.SubElement(tgt, "X").text = "15"; ET.SubElement(tgt, "Y").text = "15"
    add_item(proj_i, name="Zoom", type_name="gh_single", type_code="5").text = "1.5"
    views = ET.SubElement(dp_chunks, "chunk", name="Views")
    ET.SubElement(ET.SubElement(views, "items", count="1"), "item",
                  name="ViewCount", type_name="gh_int32", type_code="3").text = "0"

    # ── RcpLayout (confirmed from real GHX) ──────────────────────────────────
    rcp = ET.SubElement(defn_chunks, "chunk", name="RcpLayout")
    ET.SubElement(ET.SubElement(rcp, "items", count="1"), "item",
                  name="GroupCount", type_name="gh_int32", type_code="3").text = "0"

    # ── GHALibraries (Grasshopper's own entry — confirmed from real GHX) ─────
    ghal = ET.SubElement(defn_chunks, "chunk", name="GHALibraries")
    ET.SubElement(ET.SubElement(ghal, "items", count="1"), "item",
                  name="Count", type_name="gh_int32", type_code="3").text = "1"
    ghal_c = ET.SubElement(ghal, "chunks", count="1")
    lib = ET.SubElement(ghal_c, "chunk", name="Library", index="0")
    lib_i = ET.SubElement(lib, "items", count="4")
    add_item(lib_i, name="Author",  type_name="gh_string", type_code="10").text = "Robert McNeel & Associates"
    add_item(lib_i, name="Id",      type_name="gh_guid",   type_code="9").text  = "00000000-0000-0000-0000-000000000000"
    add_item(lib_i, name="Name",    type_name="gh_string", type_code="10").text = "Grasshopper"
    add_item(lib_i, name="Version", type_name="gh_string", type_code="10").text = "8.28.26041.11001"

    # ── DefinitionObjects ────────────────────────────────────────────────────
    dobj = ET.SubElement(defn_chunks, "chunk", name="DefinitionObjects")
    ET.SubElement(ET.SubElement(dobj, "items", count="1"), "item",
                  name="ObjectCount", type_name="gh_int32", type_code="3").text = str(len(objects))
    doc_chunks = ET.SubElement(dobj, "chunks", count=str(len(objects)))
    for i, obj in enumerate(objects):
        obj.index = i
        doc_chunks.append(obj.to_element())

    return root


def pretty(root):
    raw = ET.tostring(root, encoding="unicode")
    dom = parseString(raw)
    return dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


if __name__ == "__main__":
    print("Building Grasshopper Orthotic Insole Toolkit…")
    objects = build_document()
    root    = build_root(objects)
    xml_str = pretty(root)
    xml_str = xml_str.replace(
        '<?xml version="1.0" encoding="utf-8"?>',
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>'
    )

    out = "/home/user/Feet-in-Focus/Orthotic_Insole_Toolkit.ghx"
    with open(out, "w", encoding="utf-8") as f:
        f.write(xml_str)

    lines = xml_str.count("\n")
    print(f"✓  Written: {out}")
    print(f"   {lines:,} lines  (~{len(xml_str)//1024} KB)")
    print()
    print("Canvas layout (8 tool sections, left → right):")
    print("  01 Foot Scan Import & Plantar Extraction")
    print("  02 Insole Outline Generator")
    print("  03 Medial Arch Height Mapper")
    print("  04 Heel Cup Designer")
    print("  05 Metatarsal Dome Tool")
    print("  06 Posting / Wedging Tool")
    print("  07 Insole Assembly (thickness control + solid)")
    print("  08 Export-Ready Brep + 2D Rocker-Bottom Outline")
    print()
    print("Drop Orthotic_Insole_Toolkit.ghx into Grasshopper to open.")
