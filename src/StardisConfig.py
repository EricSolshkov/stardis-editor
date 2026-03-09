"""
Stardis 控制面板配置管理模块
用于保存和加载控制面板的配置
"""

import json
import os


class StardisConfig:
    """Stardis配置管理类"""
    
    def __init__(self):
        self.config = {}
    
    def save_to_file(self, filepath):
        """保存配置到JSON文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True, "配置保存成功"
        except Exception as e:
            return False, f"保存失败: {str(e)}"
    
    def load_from_file(self, filepath):
        """从JSON文件加载配置"""
        try:
            if not os.path.exists(filepath):
                return False, "配置文件不存在"
            
            with open(filepath, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            return True, "配置加载成功"
        except Exception as e:
            return False, f"加载失败: {str(e)}"
    
    def from_panel(self, panel):
        """从控制面板提取配置"""
        self.config = {
            "executable": {
                "stardis_exe_path": (panel.exe_path_edit.currentText() if hasattr(panel.exe_path_edit, 'currentText') else panel.exe_path_edit.text()),
                "working_directory": (panel.work_dir_edit.currentText() if hasattr(panel.work_dir_edit, 'currentText') else panel.work_dir_edit.text())
            },
            "basic": {
                "model_file": panel.model_file_edit.text(),
                "samples": panel.samples_spin.value(),
                "threads": panel.threads_spin.value(),
                "verbosity": panel.verbosity_combo.currentIndex()
            },
            "compute_modes": {
                "probe_vol": {
                    "enabled": panel.probe_vol_enable.isChecked(),
                    "x": panel.probe_vol_x.value(),
                    "y": panel.probe_vol_y.value(),
                    "z": panel.probe_vol_z.value(),
                    "t1": panel.probe_vol_t1.value(),
                    "t2": panel.probe_vol_t2.value()
                },
                "probe_surf": {
                    "enabled": panel.probe_surf_enable.isChecked(),
                    "x": panel.probe_surf_x.value(),
                    "y": panel.probe_surf_y.value(),
                    "z": panel.probe_surf_z.value(),
                    "side": panel.probe_surf_side.text()
                },
                "flux_surf": {
                    "enabled": panel.flux_surf_enable.isChecked(),
                    "x": panel.flux_surf_x.value(),
                    "y": panel.flux_surf_y.value(),
                    "z": panel.flux_surf_z.value()
                },
                "medium_temp": {
                    "enabled": panel.medium_temp_enable.isChecked(),
                    "name": panel.medium_name.text()
                },
                "surf_mean_temp": {
                    "enabled": panel.surf_mean_temp_enable.isChecked(),
                    "file": panel.surf_mean_temp_file.text()
                },
                "surf_temp_map": {
                    "enabled": panel.surf_temp_map_enable.isChecked(),
                    "file": panel.surf_temp_map_file.text()
                },
                "surf_flux": {
                    "enabled": panel.surf_flux_enable.isChecked(),
                    "file": panel.surf_flux_file.text()
                },
                "ir_image": {
                    "enabled": panel.ir_image_enable.isChecked(),
                    "camera": {
                        "spp": int(panel.ir_image_spp.value()),
                        "img": {"w": int(panel.ir_image_img_w.value()), "h": int(panel.ir_image_img_h.value())},
                        "fov": float(panel.ir_image_fov.value()),
                        "pos": [float(panel.ir_pos_x.value()), float(panel.ir_pos_y.value()), float(panel.ir_pos_z.value())],
                        "tgt": [float(panel.ir_tgt_x.value()), float(panel.ir_tgt_y.value()), float(panel.ir_tgt_z.value())],
                        "up": [float(panel.ir_up_x.value()), float(panel.ir_up_y.value()), float(panel.ir_up_z.value())]
                    }
                }
            },
            "advanced": {
                "diff_algo": panel.diff_algo_combo.currentIndex(),
                "picard_order": panel.picard_order_spin.value(),
                "initial_time": panel.initial_time_spin.value(),
                "disable_intrad": panel.disable_intrad_check.isChecked(),
                "rng_state_in": panel.rng_state_in.text(),
                "rng_state_out": panel.rng_state_out.text(),
                "extended_results": panel.extended_results_check.isChecked()
            },
            "output": {
                "dump_model": {
                    "enabled": panel.dump_model_enable.isChecked(),
                    "file": panel.dump_model_file.text()
                },
                "dump_chunks": {
                    "enabled": panel.dump_chunks_enable.isChecked(),
                    "prefix": panel.dump_chunks_prefix.text()
                },
                "dump_paths": {
                    "enabled": panel.dump_paths_enable.isChecked(),
                    "type": panel.dump_paths_type.currentIndex(),
                    "file": panel.dump_paths_file.text()
                },
                "green_ascii": {
                    "enabled": panel.green_ascii_enable.isChecked()
                },
                "green_bin": {
                    "enabled": panel.green_bin_enable.isChecked(),
                    "file": panel.green_bin_file.text(),
                    "end_paths": panel.green_bin_end_paths.text()
                }
            }
        }
    
    def to_panel(self, panel):
        """将配置应用到控制面板"""
        if not self.config:
            return False, "配置为空"
        
        try:
            # 可执行文件配置
            if "executable" in self.config:
                exe = self.config["executable"]
                try:
                    if hasattr(panel.exe_path_edit, 'setCurrentText'):
                        panel.exe_path_edit.setCurrentText(exe.get("stardis_exe_path", ""))
                    else:
                        panel.exe_path_edit.setText(exe.get("stardis_exe_path", ""))
                except Exception:
                    pass
                try:
                    if hasattr(panel.work_dir_edit, 'setCurrentText'):
                        panel.work_dir_edit.setCurrentText(exe.get("working_directory", ""))
                    else:
                        panel.work_dir_edit.setText(exe.get("working_directory", ""))
                except Exception:
                    pass
            
            # 基本参数
            if "basic" in self.config:
                basic = self.config["basic"]
                panel.model_file_edit.setText(basic.get("model_file", ""))
                panel.samples_spin.setValue(basic.get("samples", 1000000))
                panel.threads_spin.setValue(basic.get("threads", 4))
                panel.verbosity_combo.setCurrentIndex(basic.get("verbosity", 1))
            
            # 计算模式
            if "compute_modes" in self.config:
                modes = self.config["compute_modes"]
                
                # 体积温度探针
                if "probe_vol" in modes:
                    pv = modes["probe_vol"]
                    panel.probe_vol_enable.setChecked(pv.get("enabled", False))
                    panel.probe_vol_x.setValue(pv.get("x", 0))
                    panel.probe_vol_y.setValue(pv.get("y", 0))
                    panel.probe_vol_z.setValue(pv.get("z", 0))
                    panel.probe_vol_t1.setValue(pv.get("t1", 0))
                    panel.probe_vol_t2.setValue(pv.get("t2", 0))
                
                # 表面温度探针
                if "probe_surf" in modes:
                    ps = modes["probe_surf"]
                    panel.probe_surf_enable.setChecked(ps.get("enabled", False))
                    panel.probe_surf_x.setValue(ps.get("x", 0))
                    panel.probe_surf_y.setValue(ps.get("y", 0))
                    panel.probe_surf_z.setValue(ps.get("z", 0))
                    panel.probe_surf_side.setText(ps.get("side", ""))
                
                # 表面通量密度探针
                if "flux_surf" in modes:
                    fs = modes["flux_surf"]
                    panel.flux_surf_enable.setChecked(fs.get("enabled", False))
                    panel.flux_surf_x.setValue(fs.get("x", 0))
                    panel.flux_surf_y.setValue(fs.get("y", 0))
                    panel.flux_surf_z.setValue(fs.get("z", 0))
                
                # 介质平均温度
                if "medium_temp" in modes:
                    mt = modes["medium_temp"]
                    panel.medium_temp_enable.setChecked(mt.get("enabled", False))
                    panel.medium_name.setText(mt.get("name", ""))
                
                # 表面平均温度
                if "surf_mean_temp" in modes:
                    smt = modes["surf_mean_temp"]
                    panel.surf_mean_temp_enable.setChecked(smt.get("enabled", False))
                    panel.surf_mean_temp_file.setText(smt.get("file", ""))
                
                # 表面温度图
                if "surf_temp_map" in modes:
                    stm = modes["surf_temp_map"]
                    panel.surf_temp_map_enable.setChecked(stm.get("enabled", False))
                    panel.surf_temp_map_file.setText(stm.get("file", ""))
                
                # 表面通量
                if "surf_flux" in modes:
                    sf = modes["surf_flux"]
                    panel.surf_flux_enable.setChecked(sf.get("enabled", False))
                    panel.surf_flux_file.setText(sf.get("file", ""))
                
                # 红外图像
                if "ir_image" in modes:
                    ir = modes["ir_image"]
                    panel.ir_image_enable.setChecked(ir.get("enabled", False))
                    cam = ir.get("camera", None)
                    if isinstance(cam, dict):
                        panel.ir_image_spp.setValue(cam.get("spp", 1024))
                        img = cam.get("img", {})
                        panel.ir_image_img_w.setValue(img.get("w", 640))
                        panel.ir_image_img_h.setValue(img.get("h", 480))
                        panel.ir_image_fov.setValue(cam.get("fov", 30.0))
                        pos = cam.get("pos", [0, 0, 0])
                        panel.ir_pos_x.setValue(pos[0] if len(pos) > 0 else 0)
                        panel.ir_pos_y.setValue(pos[1] if len(pos) > 1 else 0)
                        panel.ir_pos_z.setValue(pos[2] if len(pos) > 2 else 0)
                        tgt = cam.get("tgt", [0, 0, 0])
                        panel.ir_tgt_x.setValue(tgt[0] if len(tgt) > 0 else 0)
                        panel.ir_tgt_y.setValue(tgt[1] if len(tgt) > 1 else 0)
                        panel.ir_tgt_z.setValue(tgt[2] if len(tgt) > 2 else 0)
                        up = cam.get("up", [0, 0, 1])
                        panel.ir_up_x.setValue(up[0] if len(up) > 0 else 0)
                        panel.ir_up_y.setValue(up[1] if len(up) > 1 else 0)
                        panel.ir_up_z.setValue(up[2] if len(up) > 2 else 1)
                    else:
                        try:
                            panel.ir_image_spp.setValue(1024)
                        except:
                            pass
            
            # 高级选项
            if "advanced" in self.config:
                adv = self.config["advanced"]
                panel.diff_algo_combo.setCurrentIndex(adv.get("diff_algo", 0))
                panel.picard_order_spin.setValue(adv.get("picard_order", 1))
                panel.initial_time_spin.setValue(adv.get("initial_time", 0))
                panel.disable_intrad_check.setChecked(adv.get("disable_intrad", False))
                panel.rng_state_in.setText(adv.get("rng_state_in", ""))
                panel.rng_state_out.setText(adv.get("rng_state_out", ""))
                panel.extended_results_check.setChecked(adv.get("extended_results", False))
            
            # 输出选项
            if "output" in self.config:
                out = self.config["output"]
                
                # Dump模型
                if "dump_model" in out:
                    dm = out["dump_model"]
                    panel.dump_model_enable.setChecked(dm.get("enabled", False))
                    panel.dump_model_file.setText(dm.get("file", ""))
                
                # Dump chunks
                if "dump_chunks" in out:
                    dc = out["dump_chunks"]
                    panel.dump_chunks_enable.setChecked(dc.get("enabled", False))
                    panel.dump_chunks_prefix.setText(dc.get("prefix", ""))
                
                # Dump paths
                if "dump_paths" in out:
                    dp = out["dump_paths"]
                    panel.dump_paths_enable.setChecked(dp.get("enabled", False))
                    panel.dump_paths_type.setCurrentIndex(dp.get("type", 0))
                    panel.dump_paths_file.setText(dp.get("file", ""))
                
                # Green ASCII
                if "green_ascii" in out:
                    ga = out["green_ascii"]
                    panel.green_ascii_enable.setChecked(ga.get("enabled", False))
                
                # Green 二进制
                if "green_bin" in out:
                    gb = out["green_bin"]
                    panel.green_bin_enable.setChecked(gb.get("enabled", False))
                    panel.green_bin_file.setText(gb.get("file", ""))
                    panel.green_bin_end_paths.setText(gb.get("end_paths", ""))
            
            return True, "配置应用成功"
        
        except Exception as e:
            return False, f"应用配置失败: {str(e)}"
