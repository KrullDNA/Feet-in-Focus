#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Orthotic Insole Designer — Rhino Python Plugin
===============================================
A parametric GUI panel for designing custom orthotic insoles inside Rhino.
Geometry is identical to the Grasshopper toolkit (Orthotic_Insole_Toolkit.ghx).

HOW TO RUN
----------
Option A  (quickest):
  1. Open Rhino
  2. Type  _RunScript  in the command line
  3. Browse to this file and open it
  4. The "Orthotic Insole Designer" panel appears

Option B  (toolbar button, recommended for regular use):
  1. Tools → Toolbar Layout → choose a toolbar → New Button
  2. Left-button macro:
       ! _RunScript "C:\\full\\path\\to\\OrthioticInsoleDesigner.py"
  3. Click the button any time to open the panel

BASIC WORKFLOW
--------------
  1. Draw a rough closed foot-outline curve in the Rhino Top viewport
     (or import one from an STL scan — see "Import Scan" button)
  2. Click  Pick Foot Outline  and click your curve
  3. Work through the tabs (Outline → Arch → Heel Cup → etc.) adjusting sliders
  4. Click  Preview  to see the 3-D insole in the viewport
  5. Tweak sliders, Preview again until happy
  6. Click  Bake to Rhino  — the solid is added to the document permanently
  7. Select it in Rhino → File → Export Selected → choose STL / STEP / OBJ

REQUIREMENTS
------------
  Rhino 7 or 8  (IronPython 2.7 or CPython 3)
  GH plugin NOT required — this runs as a standalone Rhino Python script.
"""

import math
import System
import Rhino
import Rhino.Geometry as rg
import Rhino.Input.Custom as ric
import Rhino.DocObjects as rdo
import Rhino.Commands as rcmd
import scriptcontext as sc

try:
    import Eto.Forms as forms
    import Eto.Drawing as drawing
    HAS_ETO = True
except ImportError:
    HAS_ETO = False


# =============================================================================
#  GEOMETRY ENGINE
#  All functions are direct ports of the 8 GHPython tools in the .ghx file.
# =============================================================================

class InsoleEngine(object):
    """Builds every piece of insole geometry from parameter values."""

    def __init__(self):
        self.flat_curve     = None   # Source foot boundary (picked by user)
        self.insole_outline = None   # Processed, offset outline
        self.arch_surface   = None
        self.heel_cup       = None
        self.dome_surface   = None
        self.rf_post        = None
        self.ff_post        = None
        self.solid          = None
        self.export_brep    = None
        self._preview_guids = []     # GUIDs of temporary preview objects

    # ------------------------------------------------------------------
    # TOOL 01  Foot Scan Import & Plantar Extraction
    # ------------------------------------------------------------------
    def extract_outline_from_mesh(self, mesh):
        """
        Given a foot-scan Mesh, flatten its plantar surface to Z=0 and
        return the largest naked-edge polyline as the foot boundary curve.
        Returns (flat_curve, info_string) or (None, error_string).
        """
        if mesh is None:
            return None, "No mesh provided."
        try:
            mesh.FaceNormals.ComputeFaceNormals()
            mesh.Normals.ComputeNormals()

            # Collect plantar faces: normal pointing downward (Z < -0.15)
            plantar = rg.Mesh()
            vmap = {}
            for fi in range(mesh.Faces.Count):
                if mesh.FaceNormals[fi].Z < -0.15:
                    face = mesh.Faces[fi]
                    vis = [face.A, face.B, face.C]
                    if not face.IsTriangle:
                        vis.append(face.D)
                    nv = []
                    for vi in vis:
                        if vi not in vmap:
                            vmap[vi] = plantar.Vertices.Count
                            plantar.Vertices.Add(mesh.Vertices[vi])
                        nv.append(vmap[vi])
                    if len(nv) == 3:
                        plantar.Faces.AddFace(nv[0], nv[1], nv[2])
                    else:
                        plantar.Faces.AddFace(nv[0], nv[1], nv[2], nv[3])

            # Fallback: lowest 6 mm band
            if plantar.Faces.Count == 0:
                bb2 = mesh.GetBoundingBox(True)
                z_low = bb2.Min.Z
                vmap2 = {}
                for fi in range(mesh.Faces.Count):
                    face = mesh.Faces[fi]
                    vis = [face.A, face.B, face.C]
                    if not face.IsTriangle:
                        vis.append(face.D)
                    if sum(1 for vi in vis if mesh.Vertices[vi].Z < z_low + 6) >= 3:
                        nv = []
                        for vi in vis:
                            if vi not in vmap2:
                                vmap2[vi] = plantar.Vertices.Count
                                plantar.Vertices.Add(mesh.Vertices[vi])
                            nv.append(vmap2[vi])
                        if len(nv) == 3:
                            plantar.Faces.AddFace(nv[0], nv[1], nv[2])
                        else:
                            plantar.Faces.AddFace(nv[0], nv[1], nv[2], nv[3])

            if plantar.Faces.Count == 0:
                return None, "Could not extract plantar surface from mesh."

            plantar.Compact()
            plantar.Normals.ComputeNormals()
            plantar.UnifyNormals()

            # Project plantar vertices to Z=0
            flat = rg.Mesh()
            for v in plantar.Vertices:
                flat.Vertices.Add(rg.Point3d(v.X, v.Y, 0.0))
            for fi in range(plantar.Faces.Count):
                f = plantar.Faces[fi]
                if f.IsTriangle:
                    flat.Faces.AddFace(f.A, f.B, f.C)
                else:
                    flat.Faces.AddFace(f.A, f.B, f.C, f.D)
            flat.Normals.ComputeNormals()
            flat.UnifyNormals()

            edges = flat.GetNakedEdges()
            if not edges:
                return None, "Could not extract boundary from flattened mesh."

            # Longest naked edge = foot perimeter
            curve = max(edges, key=lambda c: c.GetLength())
            bb = mesh.GetBoundingBox(True)
            info = ("Scan loaded  Length:{:.0f}mm  Width:{:.0f}mm  "
                    "Height:{:.0f}mm  Faces:{:d}".format(
                        bb.Max.Y - bb.Min.Y,
                        bb.Max.X - bb.Min.X,
                        bb.Max.Z - bb.Min.Z,
                        mesh.Faces.Count))
            return curve, info

        except Exception as ex:
            return None, "Scan error: " + str(ex)

    # ------------------------------------------------------------------
    # TOOL 02  Insole Outline Generator
    # ------------------------------------------------------------------
    def build_outline(self, flat_curve, offset_mm=-2.0, smoothing=0.3):
        """
        Offset and smooth the raw foot boundary to produce the insole perimeter.
        Returns (outline, heel_pt, toe_pt, length_mm, width_mm).
        """
        if flat_curve is None:
            return None, None, None, 0.0, 0.0
        try:
            crv = flat_curve
            od  = float(offset_mm) if offset_mm is not None else -2.0
            sm  = float(smoothing)  if smoothing  is not None else 0.3
            if od > 0:
                od = -od  # always inward

            # Offset (instance method on Curve)
            offs = crv.Offset(rg.Plane.WorldXY, od, 0.1,
                              rg.CurveOffsetCornerStyle.Round)
            result = offs[0] if offs else crv

            # Smooth by re-sampling + degree-3 interpolation
            if sm > 0.05:
                n   = max(24, int(60 * sm))
                dom = result.Domain
                pts = [result.PointAt(dom.ParameterAt(i / float(n)))
                       for i in range(n + 1)]
                f = rg.Curve.CreateInterpolatedCurve(pts, 3)
                if f:
                    result = f

            bb = result.GetBoundingBox(True)
            cx = (bb.Min.X + bb.Max.X) / 2.0
            length = round(bb.Max.Y - bb.Min.Y, 2)
            width  = round(bb.Max.X - bb.Min.X, 2)
            heel_pt = rg.Point3d(cx, bb.Min.Y, 0.0)
            toe_pt  = rg.Point3d(cx, bb.Max.Y, 0.0)

            self.insole_outline = result
            return result, heel_pt, toe_pt, length, width

        except Exception as ex:
            print("Outline error: " + str(ex))
            return None, None, None, 0.0, 0.0

    # ------------------------------------------------------------------
    # TOOL 03  Medial Arch Height Mapper
    # ------------------------------------------------------------------
    def build_arch(self, outline, arch_height=15.0, arch_peak=0.35,
                   arch_width=30.0, foot_side="R"):
        """
        Generate medial arch surface.  Uses a Gaussian envelope of
        semicircular arcs lofted along the foot length.
        """
        if outline is None:
            return None
        try:
            bb   = outline.GetBoundingBox(True)
            flen = bb.Max.Y - bb.Min.Y
            fwid = bb.Max.X - bb.Min.X
            ah   = float(arch_height) if arch_height is not None else 15.0
            ap   = float(arch_peak)   if arch_peak   is not None else 0.35
            aw   = float(arch_width)  if arch_width  is not None else 30.0
            side = str(foot_side).strip().upper() if foot_side else "R"

            med_x = (bb.Min.X + fwid * 0.12) if side == "R" else (bb.Max.X - fwid * 0.12)
            y0   = bb.Min.Y + 0.10 * flen
            y_pk = bb.Min.Y + ap   * flen
            y1   = bb.Min.Y + 0.72 * flen
            N    = 30
            profs = []

            for i in range(N + 1):
                t    = i / float(N)
                y    = y0 + t * (y1 - y0)
                t_pk = (y_pk - y0) / (y1 - y0) if (y1 - y0) > 0 else 0.35
                z    = max(0.0, ah * math.exp(-((t - t_pk) ** 2) / 0.06))
                if z < 0.3:
                    continue

                lw   = max(6.0, aw * (1.0 - 0.5 * abs(t - t_pk) / max(t_pk, 1 - t_pk)))
                apl  = rg.Plane(rg.Point3d(med_x, y, 0.0),
                                rg.Vector3d.XAxis, rg.Vector3d.ZAxis)
                arc  = rg.Arc(apl, lw, math.pi).ToNurbsCurve()
                # Non-uniform scale: squash arc in Z to height z
                xf   = rg.Transform.Scale(
                    rg.Plane(rg.Point3d(med_x, y, 0.0),
                             rg.Vector3d.XAxis, rg.Vector3d.ZAxis),
                    1.0, 1.0, z / lw)
                arc.Transform(xf)
                profs.append(arc)

            if len(profs) < 2:
                return None

            b = rg.Brep.CreateFromLoft(profs, rg.Point3d.Unset, rg.Point3d.Unset,
                                       rg.LoftType.Normal, False)
            result = b[0] if b else None
            self.arch_surface = result
            return result

        except Exception as ex:
            print("Arch error: " + str(ex))
            return None

    # ------------------------------------------------------------------
    # TOOL 04  Heel Cup Designer
    # ------------------------------------------------------------------
    def build_heel_cup(self, outline, cup_depth=12.0, cup_angle=15.0,
                       cup_width_pct=0.75):
        """
        Generate heel cup — a series of squashed semicircular arcs lofted
        along the heel zone (first 28% of foot length).
        """
        if outline is None:
            return None
        try:
            bb   = outline.GetBoundingBox(True)
            flen = bb.Max.Y - bb.Min.Y
            fwid = bb.Max.X - bb.Min.X
            cx   = (bb.Min.X + bb.Max.X) / 2.0
            cd   = float(cup_depth)     if cup_depth     is not None else 12.0
            ca   = float(cup_angle)     if cup_angle     is not None else 15.0
            cwp  = float(cup_width_pct) if cup_width_pct is not None else 0.75

            half_w  = fwid * cwp / 2.0
            heel_y  = bb.Min.Y
            heel_ey = bb.Min.Y + flen * 0.28
            profs   = []

            for i in range(13):
                t  = i / 12.0
                y  = heel_y + t * (heel_ey - heel_y)
                r  = half_w * math.sqrt(max(0.0, 1.0 - t ** 2))
                if r < 2.0:
                    continue
                zw   = max(0.0, cd * math.cos(math.radians(ca)) * (1.0 - 0.4 * t))
                base = rg.Point3d(cx, y, 0.0)
                arc  = rg.Arc(rg.Plane(base, rg.Vector3d.XAxis, rg.Vector3d.ZAxis),
                              r, math.pi).ToNurbsCurve()
                if r > 0:
                    xf = rg.Transform.Scale(
                        rg.Plane(base, rg.Vector3d.XAxis, rg.Vector3d.ZAxis),
                        1.0, 1.0, zw / r)
                    arc.Transform(xf)
                profs.append(arc)

            if len(profs) < 2:
                return None

            b = rg.Brep.CreateFromLoft(profs, rg.Point3d.Unset, rg.Point3d.Unset,
                                       rg.LoftType.Normal, False)
            result = b[0] if b else None
            self.heel_cup = result
            return result

        except Exception as ex:
            print("Heel cup error: " + str(ex))
            return None

    # ------------------------------------------------------------------
    # TOOL 05  Metatarsal Dome
    # ------------------------------------------------------------------
    def build_dome(self, outline, dome_height=6.0, dome_x_pct=0.5,
                   dome_y_pct=0.63, dome_radius=20.0):
        """
        Generate metatarsal support dome via surface of revolution.
        Profile = sine wave; axis = vertical line at dome centre.
        """
        if outline is None:
            return None
        try:
            bb   = outline.GetBoundingBox(True)
            flen = bb.Max.Y - bb.Min.Y
            fwid = bb.Max.X - bb.Min.X
            dh   = float(dome_height) if dome_height  is not None else 6.0
            dxp  = float(dome_x_pct)  if dome_x_pct   is not None else 0.5
            dyp  = float(dome_y_pct)  if dome_y_pct   is not None else 0.63
            dr   = float(dome_radius) if dome_radius   is not None else 20.0

            cx   = bb.Min.X + dxp * fwid
            cy   = bb.Min.Y + dyp * flen

            N = 20
            prof_pts = []
            for i in range(N + 1):
                t = i / float(N)
                prof_pts.append(
                    rg.Point3d(cx + dr * math.sin(t * math.pi),
                               cy,
                               dh * math.sin(t * math.pi)))

            pc = rg.Curve.CreateInterpolatedCurve(prof_pts, 3)
            if pc is None:
                return None

            rev = rg.RevSurface.Create(
                pc,
                rg.Line(rg.Point3d(cx, cy, 0.0), rg.Point3d(cx, cy, dh)),
                0.0, 2.0 * math.pi)
            if rev is None:
                return None

            result = rev.ToBrep()
            self.dome_surface = result
            return result

        except Exception as ex:
            print("Dome error: " + str(ex))
            return None

    # ------------------------------------------------------------------
    # TOOL 06  Posting / Wedging
    # ------------------------------------------------------------------
    def build_posting(self, outline, rf_med=0.0, rf_lat=0.0,
                      ff_med=0.0, ff_lat=0.0):
        """
        Generate rearfoot (heel) and forefoot (toe) wedge posts.
        Medial and lateral degree values independently tilt each zone.
        """
        if outline is None:
            return None, None
        try:
            bb   = outline.GetBoundingBox(True)
            flen = bb.Max.Y - bb.Min.Y
            fwid = bb.Max.X - bb.Min.X
            rmd  = float(rf_med) if rf_med is not None else 0.0
            rld  = float(rf_lat) if rf_lat is not None else 0.0
            fmd  = float(ff_med) if ff_med is not None else 0.0
            fld  = float(ff_lat) if ff_lat is not None else 0.0

            cx = (bb.Min.X + bb.Max.X) / 2.0

            def bz(x, med_d, lat_d):
                """Bottom Z at x, interpolating medial-to-lateral wedge."""
                rel = (x - cx) / (fwid / 2.0) if fwid > 0 else 0.0
                mh  = (fwid / 2.0) * math.tan(math.radians(abs(med_d)))
                lh  = (fwid / 2.0) * math.tan(math.radians(abs(lat_d)))
                return -abs(mh) * abs(rel) if rel < 0 else -abs(lh) * abs(rel)

            def wedge(y1, y2, med_d, lat_d):
                if abs(med_d) < 0.01 and abs(lat_d) < 0.01:
                    return None
                tr = rg.PolylineCurve([
                    rg.Point3d(bb.Min.X, y1, 0),
                    rg.Point3d(bb.Max.X, y1, 0),
                    rg.Point3d(bb.Max.X, y2, 0),
                    rg.Point3d(bb.Min.X, y2, 0),
                    rg.Point3d(bb.Min.X, y1, 0)])
                br = rg.PolylineCurve([
                    rg.Point3d(bb.Min.X, y1, bz(bb.Min.X, med_d, lat_d)),
                    rg.Point3d(bb.Max.X, y1, bz(bb.Max.X, med_d, lat_d)),
                    rg.Point3d(bb.Max.X, y2, bz(bb.Max.X, med_d, lat_d)),
                    rg.Point3d(bb.Min.X, y2, bz(bb.Min.X, med_d, lat_d)),
                    rg.Point3d(bb.Min.X, y1, bz(bb.Min.X, med_d, lat_d))])
                ls = rg.Brep.CreateFromLoft(
                    [tr, br], rg.Point3d.Unset, rg.Point3d.Unset,
                    rg.LoftType.Straight, False)
                return ls[0] if ls else None

            rf = wedge(bb.Min.Y,              bb.Min.Y + 0.35 * flen, rmd, rld)
            ff = wedge(bb.Min.Y + 0.65 * flen, bb.Max.Y,              fmd, fld)
            self.rf_post = rf
            self.ff_post = ff
            return rf, ff

        except Exception as ex:
            print("Posting error: " + str(ex))
            return None, None

    # ------------------------------------------------------------------
    # TOOL 07  Insole Assembly & Thickness Control
    # ------------------------------------------------------------------
    def assemble(self, outline, arch=None, heel_cup=None, dome=None,
                 rf_post=None, ff_post=None,
                 top_cover=1.5, shell=4.0, base=2.0):
        """
        Extrude the insole outline downward and join all feature BREPs.
        Returns the assembled solid Brep.
        """
        if outline is None:
            return None
        try:
            tc    = float(top_cover) if top_cover is not None else 1.5
            sh    = float(shell)     if shell     is not None else 4.0
            ba    = float(base)      if base      is not None else 2.0
            total = tc + sh + ba

            crv  = outline
            if not crv.IsClosed:
                crv = crv.ToNurbsCurve()

            # Create capped planar brep from outline, then extrude
            caps = rg.Brep.CreatePlanarBreps([crv], 0.01)
            if not caps:
                return None

            extruded = []
            for cap in caps:
                ex = cap.Faces[0].CreateExtrusion(rg.Vector3d(0, 0, -total), True)
                if ex:
                    extruded.append(ex)

            if not extruded:
                return None

            shell_brep = extruded[0]
            parts = [shell_brep]
            for g in [arch, heel_cup, dome, rf_post, ff_post]:
                if g is not None:
                    parts.append(g)

            if len(parts) > 1:
                j = rg.Brep.JoinBreps(parts, 0.1)
                solid = j[0] if j else shell_brep
            else:
                solid = shell_brep

            self.solid = solid
            return solid

        except Exception as ex:
            print("Assembly error: " + str(ex))
            return None

    # ------------------------------------------------------------------
    # TOOL 08  Export-Ready Brep + Rocker-Bottom
    # ------------------------------------------------------------------
    def build_export(self, solid, outline, rocker_angle=10.0, rocker_apex=0.5):
        """
        Merge coplanar faces for cleaner export, and generate the
        side-view rocker profile curve.
        Returns (export_brep, rocker_profile).
        """
        export_brep    = None
        rocker_profile = None
        try:
            if solid is not None:
                rep = solid.DuplicateBrep()
                rep.MergeCoplanarFaces(0.01)
                export_brep = rep

            if outline is not None:
                bb   = outline.GetBoundingBox(True)
                flen = bb.Max.Y - bb.Min.Y
                cx   = (bb.Min.X + bb.Max.X) / 2.0
                ra   = float(rocker_angle) if rocker_angle is not None else 10.0
                rap  = float(rocker_apex)  if rocker_apex  is not None else 0.50
                apex = bb.Min.Y + rap * flen
                tan_ = math.tan(math.radians(ra))

                prof_pts = [
                    rg.Point3d(cx, bb.Min.Y + i / 60.0 * flen,
                               max(0.0, -(bb.Min.Y + i / 60.0 * flen - apex)) * tan_ * -1)
                    for i in range(61)]
                rocker_profile = rg.Curve.CreateInterpolatedCurve(prof_pts, 3)

            self.export_brep = export_brep
            return export_brep, rocker_profile

        except Exception as ex:
            print("Export error: " + str(ex))
            return None, None

    # ------------------------------------------------------------------
    # Preview helpers
    # ------------------------------------------------------------------
    def _add_preview(self, geometry):
        """Add one geometry object to the doc as a temporary preview item."""
        if geometry is None:
            return
        guid = System.Guid.Empty
        if isinstance(geometry, rg.Brep):
            guid = sc.doc.Objects.AddBrep(geometry)
        elif isinstance(geometry, rg.Curve):
            guid = sc.doc.Objects.AddCurve(geometry)
        elif isinstance(geometry, rg.Mesh):
            guid = sc.doc.Objects.AddMesh(geometry)
        if guid != System.Guid.Empty:
            self._preview_guids.append(guid)

    def preview_all(self, *geoms):
        """Replace current preview with new geometry objects."""
        self.clear_preview()
        for g in geoms:
            self._add_preview(g)
        sc.doc.Views.Redraw()

    def clear_preview(self):
        """Delete all temporary preview objects from the document."""
        for guid in self._preview_guids:
            obj = sc.doc.Objects.FindId(guid)
            if obj:
                sc.doc.Objects.Delete(obj, True)
        self._preview_guids = []
        sc.doc.Views.Redraw()

    def bake(self, geometry):
        """Permanently add geometry to the Rhino document."""
        if isinstance(geometry, rg.Brep):
            sc.doc.Objects.AddBrep(geometry)
        elif isinstance(geometry, rg.Curve):
            sc.doc.Objects.AddCurve(geometry)
        sc.doc.Views.Redraw()


# =============================================================================
#  UI HELPERS
# =============================================================================

def _lbl(text, width=None):
    """Create an Eto Label."""
    lb = forms.Label()
    lb.Text = text
    if width is not None:
        lb.Width = width
    return lb


def _slider_row(layout, text, min_v, max_v, default, digits=1):
    """
    Append a  [Label | Slider | NumericStepper]  row to *layout*.
    The slider and stepper stay in sync.
    Returns the NumericStepper; read .Value for the current value.
    """
    scale = int(10 ** digits)

    lbl = forms.Label()
    lbl.Text  = text
    lbl.Width = 185

    slider = forms.Slider()
    slider.MinValue = int(min_v * scale)
    slider.MaxValue = int(max_v * scale)
    slider.Value    = int(default * scale)
    slider.Width    = 145

    num = forms.NumericStepper()
    num.MinValue      = min_v
    num.MaxValue      = max_v
    num.Value         = default
    num.DecimalPlaces = digits
    num.Increment     = 1.0 / scale
    num.Width         = 62

    # Use a mutable flag to break event feedback loops
    updating = [False]

    def on_slider(s, e):
        if updating[0]:
            return
        updating[0] = True
        num.Value = slider.Value / float(scale)
        updating[0] = False

    def on_num(s, e):
        if updating[0]:
            return
        updating[0] = True
        slider.Value = int(num.Value * scale)
        updating[0] = False

    slider.ValueChanged += on_slider
    num.ValueChanged    += on_num

    layout.BeginHorizontal()
    layout.Add(lbl)
    layout.Add(slider)
    layout.Add(num)
    layout.EndHorizontal()

    return num   # caller stores this to read .Value later


def _tab_page(title):
    """Return (TabPage, DynamicLayout) already wired together."""
    page = forms.TabPage()
    page.Text = title
    lay  = forms.DynamicLayout()
    lay.Padding = drawing.Padding(10)
    lay.Spacing = drawing.Size(3, 7)
    return page, lay


def _button(label, handler):
    b = forms.Button()
    b.Text   = label
    b.Click += handler
    return b


# =============================================================================
#  MAIN DIALOG
# =============================================================================

class InsoleDesignerForm(forms.Form):
    """
    Modeless Eto.Forms panel.
    Stays open while you interact with Rhino.
    """

    def __init__(self):
        super(InsoleDesignerForm, self).__init__()
        self.engine     = InsoleEngine()
        self.Title      = "Orthotic Insole Designer"
        self.ClientSize = drawing.Size(540, 620)
        self.Resizable  = True
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = forms.DynamicLayout()
        root.Padding = drawing.Padding(8)
        root.Spacing = drawing.Size(5, 5)

        # ── Tab control ──────────────────────────────────────────────
        tabs = forms.TabControl()
        tabs.Pages.Add(self._tab_outline())
        tabs.Pages.Add(self._tab_arch())
        tabs.Pages.Add(self._tab_heel_cup())
        tabs.Pages.Add(self._tab_metatarsal())
        tabs.Pages.Add(self._tab_posting())
        tabs.Pages.Add(self._tab_assembly())
        tabs.Pages.Add(self._tab_export())

        root.BeginVertical()
        root.Add(tabs, True, True)
        root.EndVertical()

        # ── Status bar ───────────────────────────────────────────────
        self.lbl_status = forms.Label()
        self.lbl_status.Text = "Step 1: Click 'Import Scan' or 'Pick Outline', then Preview."
        root.BeginVertical()
        root.Add(self.lbl_status)
        root.EndVertical()

        # ── Action buttons ───────────────────────────────────────────
        root.BeginHorizontal()
        root.Add(_button("Import Scan...",     self._on_import))
        root.Add(_button("Pick Outline",       self._on_pick_outline))
        root.Add(_button("Pick Mesh + Extract", self._on_pick_mesh))
        root.AddSpace()
        root.Add(_button("Preview",            self._on_preview))
        root.Add(_button("Bake to Rhino",      self._on_bake))
        root.EndHorizontal()

        self.Content = root

    # ------------------------------------------------------------------
    # Tab: Outline
    # ------------------------------------------------------------------
    def _tab_outline(self):
        page, l = _tab_page("Outline")
        l.Add(_lbl("Trim and smooth the insole border from the foot curve:"))
        self.v_offset = _slider_row(l, "Inward offset mm",          -15, 0,  -2.0, 1)
        self.v_smooth = _slider_row(l, "Smoothing (0=sharp 1=round)",  0, 1,   0.3, 2)
        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Tab: Arch
    # ------------------------------------------------------------------
    def _tab_arch(self):
        page, l = _tab_page("Arch")
        l.Add(_lbl("Medial longitudinal arch:"))
        self.v_arch_h    = _slider_row(l, "Height mm",                    0,  30, 15.0, 1)
        self.v_arch_peak = _slider_row(l, "Peak position (0=heel 1=toe)", 0,   1,  0.35, 2)
        self.v_arch_w    = _slider_row(l, "Width mm",                    10,  60, 30.0, 1)

        l.BeginHorizontal()
        l.Add(_lbl("Foot side", 185))
        self.dd_side = forms.DropDown()
        self.dd_side.DataStore   = ["Right (R)", "Left (L)"]
        self.dd_side.SelectedIndex = 0
        self.dd_side.Width = 120
        l.Add(self.dd_side)
        l.EndHorizontal()

        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Tab: Heel Cup
    # ------------------------------------------------------------------
    def _tab_heel_cup(self):
        page, l = _tab_page("Heel Cup")
        l.Add(_lbl("Heel cup geometry:"))
        self.v_cup_d = _slider_row(l, "Depth mm",               0, 25, 12.0, 1)
        self.v_cup_a = _slider_row(l, "Wall angle degrees",      0, 30, 15.0, 1)
        self.v_cup_w = _slider_row(l, "Width (0=narrow 1=full)", 0,  1,  0.75, 2)
        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Tab: Metatarsal
    # ------------------------------------------------------------------
    def _tab_metatarsal(self):
        page, l = _tab_page("Metatarsal")
        l.Add(_lbl("Metatarsal support dome:"))
        self.v_dome_h = _slider_row(l, "Height mm",              0, 15,  6.0, 1)
        self.v_dome_x = _slider_row(l, "X position (0=medial)",  0,  1,  0.5, 2)
        self.v_dome_y = _slider_row(l, "Y position (0=heel)",    0,  1,  0.63, 2)
        self.v_dome_r = _slider_row(l, "Radius mm",              5, 40, 20.0, 1)
        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Tab: Posting
    # ------------------------------------------------------------------
    def _tab_posting(self):
        page, l = _tab_page("Posting")
        l.Add(_lbl("Rearfoot wedge — heel zone (0–35%):"))
        self.v_rf_med = _slider_row(l, "Medial degrees",  0, 10, 0.0, 1)
        self.v_rf_lat = _slider_row(l, "Lateral degrees", 0, 10, 0.0, 1)
        l.Add(_lbl("Forefoot wedge — toe zone (65–100%):"))
        self.v_ff_med = _slider_row(l, "Medial degrees",  0, 10, 0.0, 1)
        self.v_ff_lat = _slider_row(l, "Lateral degrees", 0, 10, 0.0, 1)
        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Tab: Assembly
    # ------------------------------------------------------------------
    def _tab_assembly(self):
        page, l = _tab_page("Assembly")
        l.Add(_lbl("Layer thicknesses (insole = top cover + shell + base):"))
        self.v_top  = _slider_row(l, "Top cover mm", 0.5,  4, 1.5, 1)
        self.v_shell = _slider_row(l, "Shell mm",    1.0, 10, 4.0, 1)
        self.v_base  = _slider_row(l, "Base mm",     1.0,  6, 2.0, 1)

        self.lbl_total = forms.Label()
        self.lbl_total.Text = "Total thickness: 7.5 mm"
        l.Add(self.lbl_total)

        def update_total(s, e):
            t = self.v_top.Value + self.v_shell.Value + self.v_base.Value
            self.lbl_total.Text = "Total thickness: {:.1f} mm".format(t)

        self.v_top.ValueChanged   += update_total
        self.v_shell.ValueChanged += update_total
        self.v_base.ValueChanged  += update_total

        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Tab: Export
    # ------------------------------------------------------------------
    def _tab_export(self):
        page, l = _tab_page("Export")
        l.Add(_lbl("Rocker-bottom sole profile:"))
        self.v_rocker_a    = _slider_row(l, "Rocker angle degrees",      0, 25, 10.0, 1)
        self.v_rocker_apex = _slider_row(l, "Apex position (0=heel 1=toe)", 0, 1,  0.5, 2)

        l.Add(_lbl("Export format:"))
        l.BeginHorizontal()
        self.dd_fmt = forms.DropDown()
        self.dd_fmt.DataStore = [
            ".stl   —  3D Printing",
            ".step  —  CNC Milling / CAM",
            ".obj   —  General / Mesh"]
        self.dd_fmt.SelectedIndex = 0
        self.dd_fmt.Width = 200
        l.Add(self.dd_fmt)
        btn_exp = _button("Save File...", self._on_export)
        l.Add(btn_exp)
        l.EndHorizontal()

        notes = forms.Label()
        notes.Text = ("\nAfter baking:\n"
                      "  Select the insole in Rhino\n"
                      "  File \u2192 Export Selected\n"
                      "  Choose STL / STEP / OBJ")
        l.Add(notes)
        page.Content = l
        return page

    # ------------------------------------------------------------------
    # Status helper
    # ------------------------------------------------------------------
    def _status(self, msg):
        self.lbl_status.Text = msg

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_import(self, sender, e):
        """Open a file-open dialog and import a foot scan into Rhino."""
        dlg = forms.OpenFileDialog()
        dlg.Title = "Import Foot Scan"
        try:
            dlg.Filters.Add(forms.FileFilter("Mesh Files", "stl", "obj", "3dm"))
        except Exception:
            pass  # Filters are optional
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            path = dlg.FileName
            Rhino.RhinoApp.RunScript('_Import "{}" _Enter'.format(path), False)
            self._status("Imported: {}  Now click 'Pick Mesh + Extract'.".format(
                path.split("\\")[-1].split("/")[-1]))

    def _on_pick_outline(self, sender, e):
        """
        Let the user click an existing closed curve in the viewport to use
        as the foot outline.  Works with hand-drawn curves or DXF imports.
        """
        Rhino.RhinoApp.SetFocusToMainWindow()
        go = ric.GetObject()
        go.SetCommandPrompt("Select the foot outline curve (closed curve in Top view)")
        go.GeometryFilter = rdo.ObjectType.Curve
        go.Get()
        if go.CommandResult() == rcmd.Result.Success:
            crv = go.Object(0).Curve()
            if crv:
                self.engine.flat_curve = crv
                self._status("Outline set.  Adjust tabs then click Preview.")
        self.BringToFront()

    def _on_pick_mesh(self, sender, e):
        """
        Pick an imported foot-scan mesh and automatically extract the
        plantar outline curve from it.
        """
        Rhino.RhinoApp.SetFocusToMainWindow()
        go = ric.GetObject()
        go.SetCommandPrompt("Select the foot scan mesh")
        go.GeometryFilter = rdo.ObjectType.Mesh
        go.Get()
        if go.CommandResult() == rcmd.Result.Success:
            mesh = go.Object(0).Mesh()
            if mesh:
                crv, info = self.engine.extract_outline_from_mesh(mesh)
                if crv:
                    self.engine.flat_curve = crv
                    self._status("Outline extracted.  " + info)
                else:
                    self._status("Could not extract outline: " + info)
        self.BringToFront()

    def _on_preview(self, sender, e):
        """Generate all insole geometry and display it in the Rhino viewport."""
        if self.engine.flat_curve is None:
            forms.MessageBox.Show(
                "No foot outline selected.\n\n"
                "1. Draw a closed curve in Rhino (Top view)\n"
                "2. Click  'Pick Outline'  and click the curve\n\n"
                "Or import an STL and use  'Pick Mesh + Extract'.",
                "No Outline")
            return

        self._status("Generating insole…")
        try:
            # 02 Outline
            res     = self.engine.build_outline(
                self.engine.flat_curve,
                self.v_offset.Value,
                self.v_smooth.Value)
            outline = res[0]
            if outline is None:
                self._status("Outline generation failed — check that your curve is closed.")
                return

            # 03 Arch
            side = "R" if self.dd_side.SelectedIndex == 0 else "L"
            arch = self.engine.build_arch(
                outline,
                self.v_arch_h.Value, self.v_arch_peak.Value,
                self.v_arch_w.Value, side)

            # 04 Heel cup
            cup  = self.engine.build_heel_cup(
                outline,
                self.v_cup_d.Value, self.v_cup_a.Value, self.v_cup_w.Value)

            # 05 Metatarsal dome
            dome = self.engine.build_dome(
                outline,
                self.v_dome_h.Value, self.v_dome_x.Value,
                self.v_dome_y.Value, self.v_dome_r.Value)

            # 06 Posting
            rf, ff = self.engine.build_posting(
                outline,
                self.v_rf_med.Value, self.v_rf_lat.Value,
                self.v_ff_med.Value, self.v_ff_lat.Value)

            # 07 Assembly
            solid = self.engine.assemble(
                outline, arch, cup, dome, rf, ff,
                self.v_top.Value, self.v_shell.Value, self.v_base.Value)

            # 08 Export + rocker
            export, rocker = self.engine.build_export(
                solid, outline,
                self.v_rocker_a.Value, self.v_rocker_apex.Value)

            # Show in viewport
            geoms = [g for g in [export, rocker] if g is not None]
            self.engine.preview_all(*geoms)

            total = self.v_top.Value + self.v_shell.Value + self.v_base.Value
            self._status(
                "Preview done — {:.1f} mm total.  Adjust sliders or click Bake.".format(total))

        except Exception as ex:
            self._status("Error: " + str(ex))

    def _on_bake(self, sender, e):
        """Make the insole permanent in the Rhino document."""
        if self.engine.export_brep is None:
            forms.MessageBox.Show(
                "Click Preview first to generate the insole.",
                "Nothing to Bake")
            return
        self.engine.clear_preview()
        self.engine.bake(self.engine.export_brep)
        self._status("Insole baked.  Select it in Rhino, then File \u2192 Export Selected.")

    def _on_export(self, sender, e):
        """Export the baked insole solid to a file."""
        if self.engine.export_brep is None:
            forms.MessageBox.Show(
                "Click Preview → Bake → then Export.",
                "Nothing to Export")
            return
        ext_map = {0: "stl", 1: "step", 2: "obj"}
        ext = ext_map.get(self.dd_fmt.SelectedIndex, "stl")
        dlg = forms.SaveFileDialog()
        dlg.Title    = "Export Insole"
        dlg.FileName = "insole." + ext
        try:
            dlg.Filters.Add(forms.FileFilter(ext.upper() + " File", ext))
        except Exception:
            pass
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            Rhino.RhinoApp.RunScript(
                '_SelLast _Export "{}" _Enter _Enter'.format(dlg.FileName), False)
            self._status("Exported to: " + dlg.FileName)


# =============================================================================
#  ENTRY POINT
# =============================================================================

if not HAS_ETO:
    Rhino.RhinoApp.WriteLine(
        "Eto.Forms is not available.  Please use Rhino 7 or later.")
else:
    _dlg = InsoleDesignerForm()
    try:
        _dlg.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    except Exception:
        pass   # Older Rhino — no owner needed
    _dlg.Show()
