from PyQt5.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QFileDialog
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
import sys

class StlViewport(QVTKRenderWindowInteractor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = vtk.vtkRenderer()
        self.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.GetRenderWindow().GetInteractor()
        self.stl_actors = []  # 存储所有加载的actor
        self.setMinimumSize(400, 400)
        # 交互状态
        self._is_left_drag = False
        self._is_middle_drag = False
        self._last_pos = None
        # 禁用VTK默认交互器
        self.interactor.SetInteractorStyle(None)

    def load_stl(self, stl_path):
        """
        加载一个STL文件并添加到场景中，不清除已有模型。
        """
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_path)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        self.renderer.AddActor(actor)
        self.stl_actors.append(actor)
        self.renderer.ResetCamera()
        self.GetRenderWindow().Render()

    def clear_models(self):
        """
        清除所有已加载的模型。
        """
        for actor in self.stl_actors:
            self.renderer.RemoveActor(actor)
        self.stl_actors.clear()
        self.GetRenderWindow().Render()

    def mousePressEvent(self, event):
        if event.button() == 1:  # 左键
            self._is_left_drag = True
            self._last_pos = event.pos()
        elif event.button() == 4:  # 中键
            self._is_middle_drag = True
            self._last_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == 1:
            self._is_left_drag = False
        elif event.button() == 4:
            self._is_middle_drag = False
        self._last_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._last_pos is None:
            super().mouseMoveEvent(event)
            return
        dx = event.x() - self._last_pos.x()
        dy = event.y() - self._last_pos.y()
        camera = self.renderer.GetActiveCamera()
        if self._is_left_drag:
            # 左键拖动旋转
            camera.Azimuth(-dx * 0.5)
            camera.Elevation(-dy * 0.5)
            self.renderer.ResetCameraClippingRange()
            self.GetRenderWindow().Render()
        elif self._is_middle_drag:
            # 中键拖动平移
            camera.OrthogonalizeViewUp()
            camera.Dolly(1.0 + dy * 0.01)
            self.renderer.ResetCameraClippingRange()
            self.GetRenderWindow().Render()
        self._last_pos = event.pos()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        camera = self.renderer.GetActiveCamera()
        delta = event.angleDelta().y()
        factor = 1.0 + (delta / 1200.0)
        camera.Dolly(factor)
        self.renderer.ResetCameraClippingRange()
        self.GetRenderWindow().Render()
        super().wheelEvent(event)

class Inspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 400)
        self.setWindowTitle('Inspector')

