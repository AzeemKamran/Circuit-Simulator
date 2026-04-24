import sys
import json
import math
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QInputDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QToolTip, QFrame, QMessageBox, QFileDialog
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QPolygonF, QPainterPathStroker
)
from PySide6.QtCore import Qt, QRectF, QTimer, QPointF


# ── Palette ────────────────────────────────────────────────────────────────
BG        = QColor(15, 17, 24)
PANEL     = QColor(22, 25, 35)
BORDER    = QColor(44, 50, 70)
ACCENT    = QColor(0, 210, 165)
WIRE_COL  = QColor(0, 210, 165)
TEXT      = QColor(200, 215, 235)
TEXT_DIM  = QColor(90, 105, 130)
COMP_BG   = QColor(28, 33, 48)

LABEL_COLOR = {
    "R":   QColor(255, 165, 60),
    "C":   QColor(70,  180, 255),
    "L":   QColor(200, 100, 255),
    "V":   QColor(80,  230, 100),
    "I":   QColor(255, 205, 60),
    "GND": QColor(160, 185, 205),
}

GRID = 20
CW, CH = 72, 32   # component width / height


def eng(v):
    if v is None: return "?"
    if v == 0: return "0"
    exp = int(math.floor(math.log10(abs(v)) / 3) * 3)
    exp = max(-12, min(exp, 12))
    m   = v / (10 ** exp)
    sfx = {12:"T",9:"G",6:"M",3:"k",0:"",
           -3:"m",-6:"u",-9:"n",-12:"p"}.get(exp, f"e{exp}")
    return f"{m:.3g}{sfx}"

def snap(pt):
    return QPointF(round(pt.x()/GRID)*GRID, round(pt.y()/GRID)*GRID)

def qcss(col):
    return f"rgba({col.red()},{col.green()},{col.blue()},{col.alpha()})"


# ══════════════════════════════════════════════════════════════════════════
#  CircuitComponent
# ══════════════════════════════════════════════════════════════════════════
class CircuitComponent(QGraphicsItem):

    def __init__(self, label="R", value=None):
        super().__init__()
        self.label  = label
        self.value  = value
        self._v     = None
        self._i     = None
        self._hov   = False
        self._wires = []

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

    def _is_gnd(self): return self.label == "GND"

    def _size(self):
        return (28, 32) if self._is_gnd() else (CW, CH)

    def boundingRect(self):
        w, h = self._size()
        return QRectF(0, 0, w, h)

    def terminals(self):
        """Return terminal positions in scene coordinates."""
        r = self.boundingRect()
        if self._is_gnd():
            return [self.mapToScene(r.width()/2, 0)]
        return [
            self.mapToScene(0,        r.height()/2),
            self.mapToScene(r.width(), r.height()/2),
        ]

    def terminal_count(self):
        return 1 if self._is_gnd() else 2

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r   = self.boundingRect()
        col = LABEL_COLOR.get(self.label, TEXT)
        sel = self.isSelected()

        if self._is_gnd():
            cx = r.width()/2
            painter.setPen(QPen(col, 2, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(QPointF(cx, 0), QPointF(cx, 8))
            for w, yo in [(14,8),(9,13),(4,18)]:
                painter.drawLine(QPointF(cx-w, yo), QPointF(cx+w, yo))
            return

        # body
        fill = QColor(40, 46, 65) if self._hov else QColor(28, 33, 48)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(col if (sel or self._hov) else BORDER, 1.5))
        painter.drawRoundedRect(r, 5, 5)

        # symbol
        painter.setPen(QPen(col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        {
            "R": self._sym_r,
            "C": self._sym_c,
            "L": self._sym_l,
            "V": self._sym_v,
            "I": self._sym_i,
        }.get(self.label, lambda p,r: None)(painter, r)

        # label badge top-left
        painter.setPen(QPen(col, 1))
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.drawText(QRectF(3, 1, 20, 12), Qt.AlignLeft|Qt.AlignVCenter, self.label)

        # value bottom
        units = {"R":"O","C":"F","L":"H","V":"V","I":"A"}
        val = f"{eng(self.value)}{units.get(self.label,'')}" if self.value is not None else "?"
        painter.setPen(QPen(TEXT, 1))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(QRectF(0, r.height()*0.58, r.width(), r.height()*0.38),
                         Qt.AlignHCenter|Qt.AlignVCenter, val)

    def _sym_r(self, p, r):
        y = r.center().y(); x0 = r.left()+8; x1 = r.right()-8
        p.drawLine(QPointF(r.left(),y), QPointF(x0,y))
        p.drawLine(QPointF(x1,y), QPointF(r.right(),y))
        seg = (x1-x0)/6
        pts = [QPointF(x0,y)]
        for i in range(6): pts.append(QPointF(x0+(i+0.5)*seg, y+(-6 if i%2==0 else 6)))
        pts.append(QPointF(x1,y))
        path = QPainterPath(pts[0])
        for pt in pts[1:]: path.lineTo(pt)
        p.drawPath(path)

    def _sym_c(self, p, r):
        y=r.center().y(); cx=r.center().x()
        p.drawLine(QPointF(r.left(),y),QPointF(cx-5,y))
        p.drawLine(QPointF(cx+5,y),QPointF(r.right(),y))
        p.drawLine(QPointF(cx-5,y-11),QPointF(cx-5,y+11))
        p.drawLine(QPointF(cx+5,y-11),QPointF(cx+5,y+11))

    def _sym_l(self, p, r):
        y=r.center().y(); x0=r.left()+6; x1=r.right()-6; rr=(x1-x0)/4
        p.drawLine(QPointF(r.left(),y),QPointF(x0,y))
        for i in range(4): p.drawArc(QRectF(x0+i*rr,y-rr,rr,rr),0,180*16)
        p.drawLine(QPointF(x0+4*rr,y),QPointF(r.right(),y))

    def _sym_v(self, p, r):
        c=r.center(); rad=min(r.width(),r.height())/2-4
        p.drawEllipse(c,rad,rad)
        p.drawLine(QPointF(r.left(),c.y()),QPointF(c.x()-rad,c.y()))
        p.drawLine(QPointF(c.x()+rad,c.y()),QPointF(r.right(),c.y()))
        p.drawLine(QPointF(c.x()-5,c.y()-5),QPointF(c.x()-5,c.y()-1))
        p.drawLine(QPointF(c.x()-7,c.y()-3),QPointF(c.x()-3,c.y()-3))
        p.drawLine(QPointF(c.x()+3,c.y()-3),QPointF(c.x()+7,c.y()-3))

    def _sym_i(self, p, r):
        c=r.center(); rad=min(r.width(),r.height())/2-4
        p.drawEllipse(c,rad,rad)
        p.drawLine(QPointF(r.left(),c.y()),QPointF(c.x()-rad,c.y()))
        p.drawLine(QPointF(c.x()+rad,c.y()),QPointF(r.right(),c.y()))
        p.drawLine(QPointF(c.x()-5,c.y()),QPointF(c.x()+3,c.y()))
        p.drawPolygon(QPolygonF([QPointF(c.x()+3,c.y()-3),
                                  QPointF(c.x()+3,c.y()+3),
                                  QPointF(c.x()+7,c.y())]))

    def hoverEnterEvent(self, event):
        self._hov = True; self.update()
        tip = []
        if self._v is not None: tip.append(f"V = {self._v:+.4g} V")
        if self._i is not None: tip.append(f"I = {self._i:+.4g} A")
        if self._v and self._i:  tip.append(f"P = {self._v*self._i:+.4g} W")
        self.setToolTip("\n".join(tip) if tip else "No solution yet.")
        QToolTip.showText(event.screenPos().toPoint(), self.toolTip())
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hov = False; self.update(); QToolTip.hideText()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Clamp so component never leaves the safe scene area
            margin = 40
            limit  = 2800   # scene runs -3000..+3000, leave a margin
            w, h   = self._size()
            pt = value
            x  = max(-limit, min(limit - w, pt.x()))
            y  = max(-limit, min(limit - h, pt.y()))
            if x != pt.x() or y != pt.y():
                return QPointF(x, y)
            for wire in list(self._wires):
                wire.refresh()
        return super().itemChange(change, value)


# ══════════════════════════════════════════════════════════════════════════
#  Wire
# ══════════════════════════════════════════════════════════════════════════
class Wire(QGraphicsItem):

    def __init__(self, src, st):
        super().__init__()
        self.src = src; self.st = st
        self.dst = None; self.dt = None
        self._tmp = None
        self._path = QPainterPath()
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(-1)
        src._wires.append(self)

    def connect(self, dst, dt):
        self.dst = dst; self.dt = dt
        dst._wires.append(self)
        self._tmp = None
        self.refresh()

    def refresh(self):
        self.prepareGeometryChange()
        self._path = self._build()
        self.update()

    def set_tmp(self, pos):
        self._tmp = pos; self.refresh()

    def _exit_dir(self, comp, term_idx):
        """Exit direction for a terminal: +1=right, -1=left, 0=vertical (GND)."""
        if comp.label == "GND":
            return 0
        return -1 if term_idx == 0 else +1

    def _build(self):
        p1 = self.src.terminals()[self.st]
        p2 = self.dst.terminals()[self.dt] if self.dst else (self._tmp or p1)

        d1 = self._exit_dir(self.src, self.st)   # +1 right, -1 left, 0 vertical
        d2 = self._exit_dir(self.dst, self.dt) if self.dst else self._guess_entry(p1, p2)

        path = QPainterPath(p1)

        # ── GND/vertical terminals ────────────────────────────────────────
        # d1==0: src exits upward (GND top pin)
        # d2==0: dst enters from top
        if d1 == 0 and d2 == 0:
            # Both vertical: go horizontal at midpoint
            mid_y = (p1.y() + p2.y()) / 2
            path.lineTo(QPointF(p1.x(), mid_y))
            path.lineTo(QPointF(p2.x(), mid_y))
            path.lineTo(p2)
            return path

        if d1 == 0:
            # src exits vertically (upward), dst is horizontal
            # go vertical to p2.y, then horizontal
            STUB = max(20.0, abs(p2.x() - p1.x()) * 0.15)
            x_exit = p2.x() + d2 * STUB
            mid_y  = (p1.y() + p2.y()) / 2
            path.lineTo(QPointF(p1.x(), mid_y))
            path.lineTo(QPointF(x_exit, mid_y))
            path.lineTo(QPointF(x_exit, p2.y()))
            path.lineTo(p2)
            return path

        if d2 == 0:
            # dst exits vertically, src is horizontal
            STUB = max(20.0, abs(p2.x() - p1.x()) * 0.15)
            x_exit = p1.x() + d1 * STUB
            mid_y  = (p1.y() + p2.y()) / 2
            path.lineTo(QPointF(x_exit, p1.y()))
            path.lineTo(QPointF(x_exit, mid_y))
            path.lineTo(QPointF(p2.x(), mid_y))
            path.lineTo(p2)
            return path

        # ── Both horizontal terminals ─────────────────────────────────────
        dx  = p2.x() - p1.x()
        dy  = p2.y() - p1.y()
        adx = abs(dx); ady = abs(dy)

        # Minimum stub length — wire MUST exit in the correct direction
        # even if the other component is behind us
        MIN_STUB = 24.0
        stub1 = max(MIN_STUB, adx * 0.22)
        stub2 = max(MIN_STUB, adx * 0.22)

        # Exit point: guaranteed to travel d1/d2 direction away from terminal
        ex1 = p1.x() + d1 * stub1   # where wire leaves src horizontally
        ex2 = p2.x() + d2 * stub2   # where wire approaches dst horizontally

        # If nearly same Y → just horizontal segments (no vertical needed)
        if ady < 2:
            path.lineTo(QPointF(ex1, p1.y()))
            path.lineTo(QPointF(ex2, p2.y()))
            path.lineTo(p2)
            return path

        mid_y = (p1.y() + p2.y()) / 2.0

        # Terminals face each other and have room for a single-bend L
        facing = (d1 * dx > 0) and (d2 * (-dx) > 0)  # d2 points away from p2 toward p1
        room   = adx > (stub1 + stub2) * 1.1

        if facing and room:
            # Single bend at horizontal midpoint — cleanest possible route
            mx = (p1.x() + p2.x()) / 2.0
            path.lineTo(QPointF(mx, p1.y()))
            path.lineTo(QPointF(mx, p2.y()))
            path.lineTo(p2)
        else:
            # S-bend with enforced exit stubs — handles back-to-back,
            # side-by-side, overlapping, and reversed cases correctly
            path.lineTo(QPointF(ex1, p1.y()))
            path.lineTo(QPointF(ex1, mid_y))
            path.lineTo(QPointF(ex2, mid_y))
            path.lineTo(QPointF(ex2, p2.y()))
            path.lineTo(p2)

        return path

    @staticmethod
    def _guess_entry(p1, p2):
        """For a live (unfinished) wire, guess what entry direction to aim at."""
        dx = p2.x() - p1.x()
        return +1 if dx >= 0 else -1

    def boundingRect(self):
        return self._path.boundingRect().adjusted(-8,-8,8,8)

    def shape(self):
        s = QPainterPathStroker(); s.setWidth(14)
        return s.createStroke(self._path)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        col = QColor(ACCENT) if self.isSelected() else WIRE_COL
        painter.setPen(QPen(col, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._path)
        if self.dst:
            painter.setBrush(QBrush(col)); painter.setPen(Qt.NoPen)
            for pt in [self.src.terminals()[self.st], self.dst.terminals()[self.dt]]:
                painter.drawEllipse(pt, 4, 4)


# ══════════════════════════════════════════════════════════════════════════
#  MNA Solver
# ══════════════════════════════════════════════════════════════════════════
class MNASolver:
    def solve(self, comps, wires):
        term_node = {}; uid = [0]
        def node(c, t):
            k = (id(c), t)
            if k not in term_node: term_node[k] = uid[0]; uid[0] += 1
            return term_node[k]
        for c in comps:
            for t in range(c.terminal_count()): node(c, t)
        for w in wires:
            if not w.dst: continue
            k1=(id(w.src),w.st); k2=(id(w.dst),w.dt)
            if k1 not in term_node or k2 not in term_node: continue
            a,b = term_node[k1], term_node[k2]
            if a != b:
                for k in term_node:
                    if term_node[k]==b: term_node[k]=a
        uniq = sorted(set(term_node.values()))
        remap = {o:n for n,o in enumerate(uniq)}
        for k in term_node: term_node[k]=remap[term_node[k]]
        N = len(uniq)
        if N < 2: return None
        gnd = next((term_node[(id(c),0)] for c in comps if c.label=="GND"
                    if (id(c),0) in term_node), 0)
        vsrcs = [c for c in comps if c.label=="V" and c.value is not None]
        M=len(vsrcs); S=N+M
        G=np.zeros((S,S)); rhs=np.zeros(S)
        def sg(a,b,g): G[a,a]+=g;G[b,b]+=g;G[a,b]-=g;G[b,a]-=g
        for c in comps:
            if c.label=="GND": continue
            n0=term_node.get((id(c),0)); n1=term_node.get((id(c),1))
            if n0 is None or n1 is None: continue
            if c.label=="R" and c.value: sg(n0,n1,1/c.value)
            elif c.label=="L": sg(n0,n1,1/1e-9)
            elif c.label=="I" and c.value is not None:
                rhs[n0]-=c.value; rhs[n1]+=c.value
        for idx,c in enumerate(vsrcs):
            n0=term_node.get((id(c),0)); n1=term_node.get((id(c),1))
            if n0 is None or n1 is None: continue
            row=N+idx
            G[row,n0]=1;G[row,n1]=-1;G[n0,row]=1;G[n1,row]=-1;rhs[row]=c.value
        G[gnd,:]=0;G[gnd,gnd]=1;rhs[gnd]=0
        try: x=np.linalg.solve(G,rhs)
        except: x,*_=np.linalg.lstsq(G,rhs,rcond=None)
        Vn=x[:N]; res={}; vi=0
        for c in comps:
            if c.label=="GND": res[id(c)]=(0.,None); continue
            n0=term_node.get((id(c),0)); n1=term_node.get((id(c),1))
            if n0 is None or n1 is None: res[id(c)]=(None,None); continue
            vd=Vn[n0]-Vn[n1]
            if c.label=="R": res[id(c)]=(abs(vd),vd/c.value if c.value else None)
            elif c.label=="V": res[id(c)]=(abs(vd),x[N+vi] if vi<M else None); vi+=1
            elif c.label=="C": res[id(c)]=(abs(vd),0.)
            elif c.label=="L": res[id(c)]=(0.,vd/1e-9)
            elif c.label=="I": res[id(c)]=(abs(vd),c.value)
            else: res[id(c)]=(abs(vd),None)
        return res


# ══════════════════════════════════════════════════════════════════════════
#  Canvas
# ══════════════════════════════════════════════════════════════════════════
class Canvas(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(BG))
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._wire  = None
        self._pan   = False; self._pan_pt = None
        self._grid  = True
        self.msg_fn = None
        self._solver = MNASolver()
        t = QTimer(self); t.timeout.connect(self._solve); t.start(500)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self._grid: return
        painter.setPen(QPen(QColor(28,34,50),1))
        l=int(rect.left())-int(rect.left())%GRID
        t=int(rect.top()) -int(rect.top()) %GRID
        for x in range(l, int(rect.right())+GRID, GRID):
            painter.drawLine(x,int(rect.top()),x,int(rect.bottom()))
        for y in range(t, int(rect.bottom())+GRID, GRID):
            painter.drawLine(int(rect.left()),y,int(rect.right()),y)

    def _sp(self, e):
        p = e.position() if hasattr(e,"position") else QPointF(e.pos())
        return self.mapToScene(p.toPoint())

    def _near(self, sp, tol=14):
        for it in self.scene().items():
            if isinstance(it, CircuitComponent):
                for idx, pt in enumerate(it.terminals()):
                    if (pt-sp).manhattanLength()<tol: return it,idx
        return None,None

    def wheelEvent(self, e):
        f=1.15 if e.angleDelta().y()>0 else 1/1.15; self.scale(f,f)

    def mousePressEvent(self, e):
        sp=self._sp(e)
        if e.button()==Qt.MiddleButton:
            self._pan=True; self._pan_pt=e.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor); return
        if e.button()==Qt.LeftButton:
            if self._wire:
                c,t=self._near(sp)
                if c and (c,t)!=(self._wire.src,self._wire.st):
                    self._wire.connect(c,t); self._say("Wire connected.")
                else:
                    self.scene().removeItem(self._wire); self._say("Wire cancelled.")
                self._wire=None; return
            c,t=self._near(sp)
            if c:
                w=Wire(c,t); self.scene().addItem(w)
                self._wire=w; self._say("Click another terminal to finish. ESC to cancel."); return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        sp=self._sp(e)
        if self._pan and self._pan_pt:
            d=e.position().toPoint()-self._pan_pt; self._pan_pt=e.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-d.y()); return
        if self._wire: self._wire.set_tmp(snap(sp))
        c,_=self._near(sp)
        self.setCursor(Qt.CrossCursor if c else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button()==Qt.MiddleButton: self._pan=False; self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        sp=self._sp(e); it=self.scene().itemAt(sp,self.transform())
        if isinstance(it,CircuitComponent): self._edit(it); return
        if isinstance(it,Wire): self.scene().removeItem(it); return
        super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete,Qt.Key_Backspace):
            for it in list(self.scene().selectedItems()):
                if isinstance(it,CircuitComponent):
                    for w in list(self.scene().items()):
                        if isinstance(w,Wire) and (w.src==it or w.dst==it):
                            self.scene().removeItem(w)
                self.scene().removeItem(it)
        elif e.key()==Qt.Key_Escape:
            if self._wire: self.scene().removeItem(self._wire); self._wire=None; self._say("Cancelled.")
        elif e.key()==Qt.Key_G: self._grid=not self._grid; self.scene().update()
        super().keyPressEvent(e)

    def add_component(self, label):
        vc=self.viewport().rect().center()
        pt=snap(self.mapToScene(vc))
        c=CircuitComponent(label=label)
        c.setPos(pt)
        self.scene().addItem(c)
        self._say(f"Added {label} — double-click to set value.")

    def _edit(self, c):
        prompts={"R":"Resistance (Ohm)","C":"Capacitance (F)",
                 "L":"Inductance (H)","V":"Voltage (V)","I":"Current (A)"}
        if c.label not in prompts: return
        cur=str(c.value) if c.value is not None else ""
        txt,ok=QInputDialog.getText(self,f"Set {c.label}",prompts[c.label]+":",text=cur)
        if ok:
            try: c.value=float(txt); c.update(); self._say(f"{c.label} updated.")
            except: self._say("Invalid number.")

    def _solve(self):
        comps=[i for i in self.scene().items() if isinstance(i,CircuitComponent)]
        wires=[i for i in self.scene().items() if isinstance(i,Wire) and i.dst]
        res=self._solver.solve(comps,wires)
        for c in comps:
            if res and id(c) in res: c._v,c._i=res[id(c)]
            else: c._v=c._i=None

    def remove_selected(self):
        """Delete all selected items and their attached wires."""
        for it in list(self.scene().selectedItems()):
            if isinstance(it, CircuitComponent):
                for w in list(self.scene().items()):
                    if isinstance(w, Wire) and (w.src == it or w.dst == it):
                        self.scene().removeItem(w)
            self.scene().removeItem(it)
        self._say("Selected items removed.")

    def clear(self): self.scene().clear(); self._wire=None

    def save(self, path):
        comps=[i for i in self.scene().items() if isinstance(i,CircuitComponent)]
        wires=[i for i in self.scene().items() if isinstance(i,Wire) and i.dst]
        ci={id(c):n for n,c in enumerate(comps)}
        data={"comps":[{"label":c.label,"value":c.value,"x":c.pos().x(),"y":c.pos().y()} for c in comps],
              "wires":[{"sc":ci[id(w.src)],"st":w.st,"dc":ci[id(w.dst)],"dt":w.dt}
                       for w in wires if id(w.src) in ci and id(w.dst) in ci]}
        with open(path,"w") as f: json.dump(data,f,indent=2)

    def load(self, path):
        self.clear()
        with open(path) as f: data=json.load(f)
        comps=[]
        for cd in data["comps"]:
            c=CircuitComponent(label=cd["label"],value=cd["value"])
            c.setPos(cd["x"],cd["y"]); self.scene().addItem(c); comps.append(c)
        for wd in data["wires"]:
            w=Wire(comps[wd["sc"]],wd["st"])
            w.connect(comps[wd["dc"]],wd["dt"]); self.scene().addItem(w)

    def _say(self, t):
        if self.msg_fn: self.msg_fn(t)


# ══════════════════════════════════════════════════════════════════════════
#  Sidebar
# ══════════════════════════════════════════════════════════════════════════
class Sidebar(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.cv=canvas
        self.setFixedWidth(158)
        self.setStyleSheet(f"background:{qcss(PANEL)};")
        lay=QVBoxLayout(self); lay.setContentsMargins(10,14,10,14); lay.setSpacing(5)

        t=QLabel("CIRCUIT"); t.setFont(QFont("Consolas",13,QFont.Black))
        t.setStyleSheet(f"color:{qcss(ACCENT)};letter-spacing:3px;"); lay.addWidget(t)
        s=QLabel("SIMULATOR  v2"); s.setFont(QFont("Consolas",7))
        s.setStyleSheet(f"color:{qcss(TEXT_DIM)};letter-spacing:2px;margin-top:-4px;"); lay.addWidget(s)
        lay.addSpacing(8); lay.addWidget(self._sep())

        lay.addWidget(self._hdr("COMPONENTS"))
        for lbl,col,tip in [
            ("R",LABEL_COLOR["R"],"Resistor"),
            ("C",LABEL_COLOR["C"],"Capacitor"),
            ("L",LABEL_COLOR["L"],"Inductor"),
            ("V",LABEL_COLOR["V"],"DC Voltage Source"),
            ("I",LABEL_COLOR["I"],"DC Current Source"),
            ("GND",LABEL_COLOR["GND"],"Ground"),
        ]:
            lay.addWidget(self._cbtn(lbl,col,tip))

        lay.addSpacing(6); lay.addWidget(self._sep()); lay.addWidget(self._hdr("ACTIONS"))
        for txt,fn in [("Save",self._save),("Load",self._load),
                       ("Remove Selected",self._remove),("Clear All",self._clear)]:
            lay.addWidget(self._abtn(txt,fn))

        lay.addStretch(); lay.addWidget(self._sep())
        h=QLabel("DBL-CLICK  edit value\nDEL/BTN    delete item\nESC          cancel wire\nSCROLL    zoom in/out\nMID-BTN   pan canvas\nG               toggle grid")
        h.setFont(QFont("Consolas",7))
        h.setStyleSheet(f"color:{qcss(TEXT_DIM)};"); lay.addWidget(h)

    def _sep(self):
        f=QFrame(); f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"color:{qcss(BORDER)};"); return f

    def _hdr(self, t):
        l=QLabel(t); l.setFont(QFont("Consolas",7))
        l.setStyleSheet(f"color:{qcss(TEXT_DIM)};letter-spacing:2px;margin-top:4px;"); return l

    def _cbtn(self, lbl, col, tip):
        btn=QPushButton(f"  {lbl}   {tip}")
        btn.setFixedHeight(38); btn.setToolTip(tip); btn.setCursor(Qt.PointingHandCursor)
        c=qcss(col)
        btn.setStyleSheet(f"""
            QPushButton{{background:{qcss(COMP_BG)};color:{qcss(TEXT)};
                border:1px solid {qcss(BORDER)};border-left:3px solid {c};
                border-radius:4px;font-family:Consolas;font-size:11px;
                text-align:left;padding-left:6px;}}
            QPushButton:hover{{background:{qcss(BORDER)};color:white;border-left:3px solid {c};}}
        """)
        btn.clicked.connect(lambda _,l=lbl: self.cv.add_component(l))
        return btn

    def _abtn(self, txt, fn):
        btn=QPushButton(txt); btn.setFixedHeight(32); btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton{{background:{qcss(COMP_BG)};color:{qcss(TEXT)};
                border:1px solid {qcss(BORDER)};border-radius:4px;
                font-family:Consolas;font-size:10px;letter-spacing:1px;}}
            QPushButton:hover{{background:{qcss(BORDER)};color:white;}}
        """)
        btn.clicked.connect(fn); return btn

    def _remove(self):
        self.cv.remove_selected()

    def _save(self):
        p,_=QFileDialog.getSaveFileName(self,"Save","","JSON (*.json)")
        if p: self.cv.save(p)
    def _load(self):
        p,_=QFileDialog.getOpenFileName(self,"Load","","JSON (*.json)")
        if p: self.cv.load(p)
    def _clear(self):
        if QMessageBox.question(self,"Clear","Clear the canvas?")==QMessageBox.Yes:
            self.cv.clear()


# ══════════════════════════════════════════════════════════════════════════
#  Status bar
# ══════════════════════════════════════════════════════════════════════════
class StatusBar(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedHeight(26)
        self.setStyleSheet(f"background:{qcss(PANEL)};border-top:1px solid {qcss(BORDER)};")
        lay=QHBoxLayout(self); lay.setContentsMargins(12,0,12,0)
        self._l=QLabel("Ready — click a component in the sidebar to place it.")
        self._l.setFont(QFont("Consolas",8))
        self._l.setStyleSheet(f"color:{qcss(ACCENT)};"); lay.addWidget(self._l)
        lay.addStretch()
        r=QLabel("MNA DC Solver"); r.setFont(QFont("Consolas",8))
        r.setStyleSheet(f"color:{qcss(TEXT_DIM)};"); lay.addWidget(r)
    def msg(self,t): self._l.setText(t)


# ══════════════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circuit Simulator")
        self.resize(1200,800)
        self.setStyleSheet(f"background:{qcss(BG)};")

        scene=QGraphicsScene(self)
        scene.setSceneRect(-3000,-3000,6000,6000)
        self._cv=Canvas(scene)
        self._sb=StatusBar()
        self._cv.msg_fn=self._sb.msg
        self._side=Sidebar(self._cv)

        body=QWidget(); hl=QHBoxLayout(body)
        hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        hl.addWidget(self._side)
        div=QFrame(); div.setFrameShape(QFrame.VLine)
        div.setStyleSheet(f"color:{qcss(BORDER)};"); hl.addWidget(div)
        hl.addWidget(self._cv)

        root=QWidget(); vl=QVBoxLayout(root)
        vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        vl.addWidget(body); vl.addWidget(self._sb)
        self.setCentralWidget(root)

    def showEvent(self, event):
        super().showEvent(event)
        self._cv.centerOn(0, 0)


if __name__ == "__main__":
    app=QApplication(sys.argv)
    app.setFont(QFont("Consolas",10))
    win=MainWindow()
    win.show()
    sys.exit(app.exec())
