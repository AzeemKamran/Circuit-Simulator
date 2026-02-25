import sys
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsItem, QInputDialog, QWidget, QVBoxLayout, QToolTip
)
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent
from PySide6.QtCore import Qt, QRectF, QTimer

class CircuitComponent(QGraphicsItem):
    def __init__(self, width=60, height=20, label="R", value=None):
        super().__init__()
        self.width = width
        self.height = height
        self.label = label
        self.value = value  # e.g., resistance, capacitance, etc.
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self.connections = [None, None]  # left, right
        self.voltage = None
        self.current = None

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(Qt.NoBrush)
        rect = self.boundingRect()
        if self.label == "R":  # Resistor
            y = rect.center().y()
            x0 = rect.left() + 5
            x1 = rect.right() - 5
            step = (x1 - x0) / 6
            points = [
                (x0, y),
                (x0 + step, y - 10),
                (x0 + 2*step, y + 10),
                (x0 + 3*step, y - 10),
                (x0 + 4*step, y + 10),
                (x0 + 5*step, y - 10),
                (x1, y)
            ]
            for i in range(len(points)-1):
                painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        elif self.label == "C":  # Capacitor
            y = rect.center().y()
            x0 = rect.left() + 15
            x1 = rect.right() - 15
            painter.drawLine(x0, y - 10, x0, y + 10)
            painter.drawLine(x1, y - 10, x1, y + 10)
            painter.drawLine(rect.left(), y, x0, y)
            painter.drawLine(x1, y, rect.right(), y)
        elif self.label == "L":  # Inductor
            y = rect.center().y()
            x0 = rect.left() + 10
            r = 10
            for i in range(4):
                painter.drawArc(x0 + i*r, y - r, r, 2*r, 0*16, 180*16)
            painter.drawLine(rect.left(), y, x0, y)
            painter.drawLine(x0 + 4*r, y, rect.right(), y)
        elif self.label == "V":  # DC Source
            center = rect.center()
            radius = 14
            painter.drawEllipse(center, radius, radius)
            painter.drawLine(rect.left(), center.y(), center.x() - radius, center.y())
            painter.drawLine(center.x() + radius, center.y(), rect.right(), center.y())
            painter.drawLine(center.x() - 6, center.y() - 6, center.x() - 6, center.y() - 2)
            painter.drawLine(center.x() - 8, center.y() - 4, center.x() - 4, center.y() - 4)
            painter.drawLine(center.x() - 6, center.y() + 4, center.x() - 2, center.y() + 4)
        else:
            painter.setBrush(QColor(80, 80, 80))
            painter.drawRect(rect)
        # Draw label and value
        painter.setPen(QPen(Qt.white, 1))
        painter.drawText(rect, Qt.AlignBottom | Qt.AlignHCenter, self.label)
        if self.value is not None:
            painter.drawText(rect, Qt.AlignTop | Qt.AlignHCenter, str(self.value))

    def update_tooltip(self):
        tip = []
        if self.voltage is not None:
            tip.append(f"V = {self.voltage:.2f} V")
        if self.current is not None:
            tip.append(f"I = {self.current:.2f} A")
        # Capacitor: Q = C * V
        if self.label == "C" and self.value is not None and self.voltage is not None:
            q = self.value * self.voltage
            tip.append(f"Q = {q:.4e} C (charge)")
        # Inductor: E = 0.5 * L * I^2
        if self.label == "L" and self.value is not None and self.current is not None:
            energy = 0.5 * self.value * self.current ** 2
            tip.append(f"E = {energy:.4e} J (energy)")
        if not tip:
            tip.append("No solution or incomplete circuit.")
        self.setToolTip('\n'.join(tip))

    def hoverEnterEvent(self, event):
        # Show tooltip at mouse position (no .toPoint() needed)
        QToolTip.showText(event.screenPos(), self.toolTip())
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    def connection_points(self):
        # Returns the center left and right points for wiring
        rect = self.boundingRect()
        left = self.mapToScene(rect.left(), rect.center().y())
        right = self.mapToScene(rect.right(), rect.center().y())
        return [left, right]

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QWidget

class Wire(QGraphicsItem):
    def __init__(self, start_item, start_terminal, end_item=None, end_terminal=None):
        super().__init__()
        self.start_item = start_item
        self.start_terminal = start_terminal  # 0=left, 1=right
        self.end_item = end_item
        self.end_terminal = end_terminal
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self._temp_end = None

    def boundingRect(self):
        if self.end_item is not None:
            p1 = self.start_item.connection_points()[self.start_terminal]
            p2 = self.end_item.connection_points()[self.end_terminal]
        else:
            p1 = self.start_item.connection_points()[self.start_terminal]
            p2 = self._temp_end if self._temp_end else p1
        return QRectF(p1, p2).normalized().adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget):
        painter.setPen(QPen(Qt.yellow, 3))
        if self.end_item is not None:
            p1 = self.start_item.connection_points()[self.start_terminal]
            p2 = self.end_item.connection_points()[self.end_terminal]
        else:
            p1 = self.start_item.connection_points()[self.start_terminal]
            p2 = self._temp_end if self._temp_end else p1
        painter.drawLine(p1, p2)

    def set_temp_end(self, pos):
        self._temp_end = pos
        self.update()


class CircuitView(QGraphicsView):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            for item in self.scene().selectedItems():
                # Remove wires connected to this component
                if isinstance(item, CircuitComponent):
                    wires_to_remove = []
                    for wire in self.scene().items():
                        if isinstance(wire, Wire) and (wire.start_item == item or wire.end_item == item):
                            wires_to_remove.append(wire)
                    for wire in wires_to_remove:
                        self.scene().removeItem(wire)
                self.scene().removeItem(item)
            return
        super().keyPressEvent(event)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(30, 32, 40))
        self.circuit_graph = {}  # node: [connected nodes]
        self._pending_wire_start = None  # (component, terminal)
        self._solve_timer = QTimer()
        self._solve_timer.setInterval(500)
        self._solve_timer.timeout.connect(self.solve_circuit)
        self._solve_timer.start()

    def solve_circuit(self):
        # Gather all components and wires
        components = [item for item in self.scene().items() if isinstance(item, CircuitComponent)]
        wires = [item for item in self.scene().items() if isinstance(item, Wire)]
        # Build a netlist: assign a node number to each terminal
        node_map = {}  # (component, terminal) -> node_id
        node_id = 0
        # Find all unique nodes by traversing connections
        def find_or_create_node(comp, term):
            key = (id(comp), term)
            if key not in node_map:
                nonlocal node_id
                node_map[key] = node_id
                node_id += 1
            return node_map[key]
        for wire in wires:
            n1 = find_or_create_node(wire.start_item, wire.start_terminal)
            n2 = find_or_create_node(wire.end_item, wire.end_terminal)
            # Merge nodes
            for k, v in list(node_map.items()):
                if v == n2:
                    node_map[k] = n1
        # Reindex nodes to be contiguous
        node_ids = list(set(node_map.values()))
        node_remap = {nid: i for i, nid in enumerate(node_ids)}
        for k in node_map:
            node_map[k] = node_remap[node_map[k]]
        n_nodes = len(set(node_map.values()))
        if n_nodes < 2:
            # Not enough nodes to solve
            for comp in components:
                comp.voltage = None
                comp.current = None
                comp.update_tooltip()
            return
        # Build equations (assume one voltage source, series/parallel resistors/capacitors/inductors)
        # Only DC: capacitors = open, inductors = short (0 ohm)
        eqs = []
        rhs = []
        comp_info = []
        for comp in components:
            # Get node numbers for each terminal
            n1 = node_map.get((id(comp), 0), None)
            n2 = node_map.get((id(comp), 1), None)
            if n1 is None or n2 is None:
                continue
            if comp.label == "R":
                if comp.value is None or comp.value == 0:
                    continue
                # I = (Vn1 - Vn2)/R
                row = [0]*n_nodes
                row[n1] = 1/comp.value
                row[n2] = -1/comp.value
                eqs.append(row)
                rhs.append(0)
                comp_info.append((comp, n1, n2, 'R'))
            elif comp.label == "C":
                # Capacitor: assign voltage if possible
                comp_info.append((comp, n1, n2, 'C'))
            elif comp.label == "L":
                # Inductor: assign current if possible
                comp_info.append((comp, n1, n2, 'L'))
            elif comp.label == "V":
                # Voltage source: Vn1 - Vn2 = V
                row = [0]*n_nodes
                row[n1] = 1
                row[n2] = -1
                eqs.append(row)
                rhs.append(comp.value if comp.value is not None else 0)
                comp_info.append((comp, n1, n2, 'V'))
        # Reference node (ground)
        if eqs:
            ground_row = [0]*n_nodes
            ground_row[0] = 1
            eqs.append(ground_row)
            rhs.append(0)
        try:
            A = np.array(eqs)
            b = np.array(rhs)
            if len(A) == 0:
                raise Exception("No equations")
            v = np.linalg.lstsq(A, b, rcond=None)[0]
            # Assign voltages/currents
            for comp, n1, n2, typ in comp_info:
                if typ == 'R' and comp.value:
                    comp.voltage = abs(v[n1] - v[n2])
                    comp.current = comp.voltage / comp.value
                elif typ == 'V':
                    comp.voltage = comp.value
                    comp.current = None
                elif typ == 'C':
                    # Capacitor: assign voltage across its terminals
                    comp.voltage = abs(v[n1] - v[n2])
                    comp.current = None
                elif typ == 'L':
                    # Inductor: assign current if terminals are connected (use current from a parallel wire or resistor)
                    comp.voltage = 0
                    comp.current = None
                    # Try to find a wire or resistor with same terminals
                    for c2, nn1, nn2, t2 in comp_info:
                        if t2 in ('R', 'V') and ((nn1 == n1 and nn2 == n2) or (nn1 == n2 and nn2 == n1)):
                            comp.current = c2.current
                            break
            for comp in components:
                comp.update_tooltip()
            self.viewport().update()  # Force repaint to update hover state
        except Exception as e:
            for comp in components:
                comp.voltage = None
                comp.current = None
                comp.update_tooltip()
            self.viewport().update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # Use position() for PySide6 (returns QPointF), convert to QPoint for mapToScene
        if hasattr(event, 'position'):
            pos = self.mapToScene(event.position().toPoint())
        else:
            pos = self.mapToScene(event.pos())
        # Check if double-clicked on a wire
        item = self.scene().itemAt(pos, self.transform())
        if isinstance(item, Wire):
            self.scene().removeItem(item)
            return
        # Check if double-clicked on a component
        if isinstance(item, CircuitComponent):
            self.edit_component_value(item)
            return
        self.show_component_dialog(pos)

    def edit_component_value(self, comp):
        if comp.label == "R":
            text, ok = QInputDialog.getText(self, "Set Resistance", "Enter resistance (Ω):", text=str(comp.value) if comp.value else "")
            if ok:
                try:
                    comp.value = float(text)
                    comp.update()
                except ValueError:
                    pass
        elif comp.label == "C":
            text, ok = QInputDialog.getText(self, "Set Capacitance", "Enter capacitance (F):", text=str(comp.value) if comp.value else "")
            if ok:
                try:
                    comp.value = float(text)
                    comp.update()
                except ValueError:
                    pass
        elif comp.label == "L":
            text, ok = QInputDialog.getText(self, "Set Inductance", "Enter inductance (H):", text=str(comp.value) if comp.value else "")
            if ok:
                try:
                    comp.value = float(text)
                    comp.update()
                except ValueError:
                    pass
        elif comp.label == "V":
            text, ok = QInputDialog.getText(self, "Set Voltage", "Enter voltage (V):", text=str(comp.value) if comp.value else "")
            if ok:
                try:
                    comp.value = float(text)
                    comp.update()
                except ValueError:
                    pass

    # New wiring logic
    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.position().toPoint() if hasattr(event, 'position') else event.pos())
        # Detect hover at terminal ends
        self._hovered_terminal = None
        for item in self.scene().items():
            if isinstance(item, CircuitComponent):
                for idx, pt in enumerate(item.connection_points()):
                    if (pt - pos).manhattanLength() < 15:
                        self._hovered_terminal = (item, idx)
                        self.setCursor(Qt.CrossCursor)
                        break
        if not self._hovered_terminal:
            self.setCursor(Qt.ArrowCursor)
        # If wiring in progress, update wire temp end
        if hasattr(self, '_active_wire') and self._active_wire:
            self._active_wire.set_temp_end(pos)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        pos = self.mapToScene(event.position().toPoint() if hasattr(event, 'position') else event.pos())
        # If wiring is in progress, end wiring when a terminal is clicked
        if hasattr(self, '_active_wire') and self._active_wire:
            comp, terminal = self._find_near_terminal(pos)
            if comp is not None and (comp, terminal) != self._pending_wire_start:
                start_comp, start_term = self._pending_wire_start
                self._active_wire.end_item = comp
                self._active_wire.end_terminal = terminal
                self._register_connection(start_comp, start_term, comp, terminal)
                self._active_wire = None
                self._pending_wire_start = None
                return
            # If not a terminal, ignore click during wiring
            return
        # Start wiring if hovering at terminal and not already wiring
        if hasattr(self, '_hovered_terminal') and self._hovered_terminal:
            comp, terminal = self._hovered_terminal
            self._active_wire = Wire(comp, terminal)
            self.scene().addItem(self._active_wire)
            self._pending_wire_start = (comp, terminal)
            return
        super().mousePressEvent(event)

    # Parallel connections are allowed: no restriction in _register_connection

    # No need for mouseMoveEvent for wiring now

    def _find_near_terminal(self, pos, tol=15):
        # Returns (component, terminal_index) if pos is near a terminal
        for item in self.scene().items():
            if isinstance(item, CircuitComponent):
                for idx, pt in enumerate(item.connection_points()):
                    if (pt - pos).manhattanLength() < tol:
                        return item, idx
        return None, None

    def _register_connection(self, comp1, term1, comp2, term2):
        # Add to circuit graph
        n1 = (id(comp1), term1)
        n2 = (id(comp2), term2)
        self.circuit_graph.setdefault(n1, []).append(n2)
        self.circuit_graph.setdefault(n2, []).append(n1)

    def show_component_dialog(self, pos):
        items = ["DC Source", "Resistor", "Capacitor", "Inductor", "Wire"]
        item, ok = QInputDialog.getItem(self, "Add Component or Wire", "Select:", items, 0, False)
        if not ok or not item:
            return
        if item == "Wire":
            comp, terminal = self._find_near_terminal(pos)
            if comp is not None:
                self._pending_wire_start = (comp, terminal)
            else:
                self._pending_wire_start = None
        else:
            value = None
            if item == "DC Source":
                comp = CircuitComponent(label="V", value=value)
            elif item == "Resistor":
                comp = CircuitComponent(label="R", value=value)
            elif item == "Capacitor":
                comp = CircuitComponent(label="C", value=value)
            elif item == "Inductor":
                comp = CircuitComponent(label="L", value=value)
            else:
                return
            comp.setPos(pos)
            self.scene().addItem(comp)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circuit Simulator")
        self.resize(1000, 700)

        # Create a scene and a view
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor(30, 32, 10))
        self.view = CircuitView(self.scene, self)
        self.setCentralWidget(self.view)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())