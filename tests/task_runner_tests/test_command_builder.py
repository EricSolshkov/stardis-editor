"""CommandBuilder 命令行生成测试。"""

from task_runner.command_builder import CommandBuilder
from models.task_model import (
    ComputeMode, FieldSolveType,
    StardisParams, HtppParams, AdvancedOptions, FieldSolveConfig,
    HtppMode,
)


class TestBuildStardisIR:
    """IR 渲染模式命令构建。"""

    def test_basic_ir_render(self):
        params = StardisParams(model_file="scene.txt", threads=4, verbosity=1)
        cam = {
            "position": [10.0, 20.0, 30.0],
            "target": [0.0, 0.0, 0.0],
            "up": [0.0, 0.0, 1.0],
            "fov": 45.0,
            "spp": 64,
            "resolution": [640, 480],
        }
        args = CommandBuilder.build_stardis(
            "scene.txt", ComputeMode.IR_RENDER, params, camera_snapshot=cam,
        )
        assert args[0:2] == ['-M', 'scene.txt']
        assert '-t' in args
        assert args[args.index('-t') + 1] == '4'
        assert '-R' in args
        r_val = args[args.index('-R') + 1]
        assert 'spp=64' in r_val
        assert 'img=640x480' in r_val
        assert 'fov=45.0' in r_val

    def test_ir_output_filename(self):
        cam = {"resolution": [320, 240], "spp": 128}
        name = CommandBuilder.build_ir_output_filename(cam)
        assert name == "IRR_320x240x128.ht"


class TestBuildStardisProbe:
    """探针求解模式命令构建。"""

    def test_volume_temp_probe(self):
        params = StardisParams(
            model_file="scene.txt", samples=100000, threads=2,
            probe_refs=["P1"],
        )
        probes = [
            {"name": "P1", "probe_type": "VOLUME_TEMP",
             "position": [1.0, 2.0, 3.0], "time": 5.0, "side": ""},
        ]
        args = CommandBuilder.build_stardis(
            "scene.txt", ComputeMode.PROBE_SOLVE, params,
            probe_snapshots=probes,
        )
        assert '-n' in args
        assert args[args.index('-n') + 1] == '100000'
        assert '-p' in args
        assert args[args.index('-p') + 1] == '1.0,2.0,3.0,5.0'

    def test_surface_temp_probe(self):
        params = StardisParams(model_file="s.txt", samples=10)
        probes = [
            {"name": "P2", "probe_type": "SURFACE_TEMP",
             "position": [0.0, 0.0, 0.0], "time": None, "side": "front"},
        ]
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.PROBE_SOLVE, params, probe_snapshots=probes,
        )
        assert '-P' in args
        assert args[args.index('-P') + 1] == '0.0,0.0,0.0:front'

    def test_surface_flux_probe(self):
        params = StardisParams(model_file="s.txt", samples=10)
        probes = [
            {"name": "P3", "probe_type": "SURFACE_FLUX",
             "position": [4.0, 5.0, 6.0], "time": None, "side": ""},
        ]
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.PROBE_SOLVE, params, probe_snapshots=probes,
        )
        assert '-f' in args
        assert args[args.index('-f') + 1] == '4.0,5.0,6.0'

    def test_multiple_probes(self):
        params = StardisParams(model_file="s.txt", samples=10)
        probes = [
            {"name": "A", "probe_type": "VOLUME_TEMP",
             "position": [1, 2, 3], "time": None, "side": ""},
            {"name": "B", "probe_type": "SURFACE_FLUX",
             "position": [4, 5, 6], "time": None, "side": ""},
        ]
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.PROBE_SOLVE, params, probe_snapshots=probes,
        )
        assert args.count('-p') == 1
        assert args.count('-f') == 1


class TestBuildStardisField:
    """场求解模式命令构建。"""

    def test_medium_temp(self):
        fs = FieldSolveConfig(solve_type=FieldSolveType.MEDIUM_TEMP, medium_name="air")
        params = StardisParams(model_file="s.txt", samples=10, field_solve=fs)
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.FIELD_SOLVE, params,
        )
        assert '-m' in args
        assert args[args.index('-m') + 1] == 'air'

    def test_surf_flux(self):
        fs = FieldSolveConfig(solve_type=FieldSolveType.SURF_FLUX, solve_file="flux.dat")
        params = StardisParams(model_file="s.txt", samples=10, field_solve=fs)
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.FIELD_SOLVE, params,
        )
        assert '-F' in args
        assert args[args.index('-F') + 1] == 'flux.dat'


class TestBuildAdvancedOptions:
    """高级选项命令构建。"""

    def test_all_advanced_options(self):
        adv = AdvancedOptions(
            diff_algorithm="mc",
            picard_order=3,
            initial_time=100.0,
            disable_intrad=True,
            extended_results=True,
            rng_state_in="rng_in.dat",
            rng_state_out="rng_out.dat",
        )
        params = StardisParams(model_file="s.txt", advanced=adv)
        cam = {"position": [0, 0, 0], "target": [1, 0, 0], "up": [0, 0, 1],
               "fov": 30, "spp": 32, "resolution": [320, 320]}
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.IR_RENDER, params, camera_snapshot=cam,
        )
        assert '-a' in args and args[args.index('-a') + 1] == 'mc'
        assert '-o' in args and args[args.index('-o') + 1] == '3'
        assert '-I' in args and args[args.index('-I') + 1] == '100.0'
        assert '-i' in args  # disable_intrad
        assert '-e' in args  # extended_results
        assert '-x' in args and args[args.index('-x') + 1] == 'rng_in.dat'
        assert '-X' in args and args[args.index('-X') + 1] == 'rng_out.dat'

    def test_default_advanced_options_empty(self):
        params = StardisParams(model_file="s.txt")
        cam = {"position": [0, 0, 0], "target": [1, 0, 0], "up": [0, 0, 1],
               "fov": 30, "spp": 32, "resolution": [320, 320]}
        args = CommandBuilder.build_stardis(
            "s.txt", ComputeMode.IR_RENDER, params, camera_snapshot=cam,
        )
        # 默认值不应产生高级选项
        assert '-a' not in args
        assert '-e' not in args
        assert '-x' not in args


class TestBuildHtpp:
    """HTPP 命令构建。"""

    def test_image_mode(self):
        params = HtppParams(
            threads=2, exposure=1.5, white_scale=5000.0,
            force_overwrite=True, output_file="out.png",
        )
        args = CommandBuilder.build_htpp(HtppMode.IMAGE, params, "input.ht")
        assert '-t' in args and args[args.index('-t') + 1] == '2'
        assert '-f' in args
        assert '-i' in args
        img_opts = args[args.index('-i') + 1]
        assert 'exposure=1.5' in img_opts
        assert 'white=5000.0' in img_opts
        assert 'input.ht' in args
        assert '-o' in args and args[args.index('-o') + 1] == 'out.png'

    def test_argument_order(self):
        """验证参数顺序：[-fv] [-i/-m] [-o] [-t] [input]"""
        params = HtppParams(
            threads=4, exposure=2.0, force_overwrite=True,
            verbose=True, output_file="out.png",
        )
        args = CommandBuilder.build_htpp(HtppMode.IMAGE, params, "data.ht")
        idx_f = args.index('-f')
        idx_v = args.index('-v')
        idx_i = args.index('-i')
        idx_o = args.index('-o')
        idx_t = args.index('-t')
        # input 是最后一个元素
        assert args[-1] == 'data.ht'
        # 顺序：flags < -i < -o < -t < input
        assert idx_f < idx_i
        assert idx_v < idx_i
        assert idx_i < idx_o
        assert idx_o < idx_t
        assert idx_t < len(args) - 1

    def test_image_mode_no_white_scale(self):
        """exposure 非默认值时才出现 -i"""
        params = HtppParams(exposure=2.0, white_scale=None)
        args = CommandBuilder.build_htpp(HtppMode.IMAGE, params, "input.ht")
        img_opts = args[args.index('-i') + 1]
        assert img_opts == 'exposure=2.0'
        assert 'white=' not in img_opts

    def test_image_mode_all_defaults(self):
        """全默认参数时不应产生 -i 标志"""
        params = HtppParams(exposure=1.0, white_scale=None)
        args = CommandBuilder.build_htpp(HtppMode.IMAGE, params, "input.ht")
        assert '-i' not in args
        assert args[-1] == 'input.ht'

    def test_map_mode(self):
        params = HtppParams(
            pixel_component=3, palette="jet",
            range_min=200.0, range_max=400.0, gnuplot=True,
        )
        args = CommandBuilder.build_htpp(HtppMode.MAP, params, "data.ht")
        assert '-m' in args
        map_opts = args[args.index('-m') + 1]
        assert 'pixcpnt=3' in map_opts
        assert 'palette=jet' in map_opts
        assert 'range=200.0,400.0' in map_opts
        assert 'gnuplot' in map_opts

    def test_map_mode_minimal(self):
        """全默认 map 参数时不应产生 -m 标志"""
        params = HtppParams(pixel_component=0)
        args = CommandBuilder.build_htpp(HtppMode.MAP, params, "data.ht")
        assert '-m' not in args
        assert args[-1] == 'data.ht'

    def test_map_mode_non_default_pixcpnt(self):
        params = HtppParams(pixel_component=3)
        args = CommandBuilder.build_htpp(HtppMode.MAP, params, "data.ht")
        assert '-m' in args
        map_opts = args[args.index('-m') + 1]
        assert map_opts == 'pixcpnt=3'

    def test_single_thread_no_flag(self):
        params = HtppParams(threads=1, exposure=1.0)
        args = CommandBuilder.build_htpp(HtppMode.IMAGE, params, "x.ht")
        assert '-t' not in args
        assert '-i' not in args  # exposure=1.0 是默认值
