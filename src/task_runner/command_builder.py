"""
CommandBuilder — 将 ResolvedTask 转为可执行的命令行参数列表。
"""

from typing import List, Optional

from models.task_model import (
    ComputeMode, FieldSolveType, HtppMode,
    StardisParams, HtppParams, AdvancedOptions, FieldSolveConfig,
)


class CommandBuilder:
    """将解析后的任务参数转为命令行参数列表（不含 exe 路径）。"""

    @staticmethod
    def build_stardis(model_file: str, compute_mode: ComputeMode,
                      params: StardisParams,
                      camera_snapshot: Optional[dict] = None,
                      probe_snapshots: Optional[List[dict]] = None) -> List[str]:
        """构建 stardis 参数列表。"""
        args = []

        # -M 模型文件（必需）
        args.extend(['-M', model_file])

        # 线程
        if params.threads > 1:
            args.extend(['-t', str(params.threads)])

        # 详细度
        if params.verbosity > 0:
            args.extend(['-V', str(params.verbosity)])

        # 模式专有参数
        if compute_mode == ComputeMode.IR_RENDER and camera_snapshot:
            args.extend(CommandBuilder._build_ir_args(camera_snapshot))
        elif compute_mode == ComputeMode.PROBE_SOLVE and probe_snapshots:
            args.extend(['-n', str(params.samples)])
            args.extend(CommandBuilder._build_probe_args(probe_snapshots))
        elif compute_mode == ComputeMode.FIELD_SOLVE and params.field_solve:
            args.extend(['-n', str(params.samples)])
            args.extend(CommandBuilder._build_field_args(params.field_solve))

        # 高级选项
        args.extend(CommandBuilder._build_advanced_args(params.advanced))

        return args

    @staticmethod
    def build_htpp(htpp_mode: HtppMode, params: HtppParams,
                   input_file: str) -> List[str]:
        """构建 htpp 参数列表。

        参数顺序遵循：htpp [-fhVv] [-i img_opt[:img_opt ...]] [-m map_opt[:map_opt ...]]
                            [-o output] [-t threads_count] [input]
        """
        args = []

        # 标志位 (-f, -v)
        if params.force_overwrite:
            args.append('-f')
        if params.verbose:
            args.append('-v')

        # 模式选项 (-i 或 -m)，仅非默认值时才添加
        if htpp_mode == HtppMode.IMAGE:
            img_opts = CommandBuilder._build_image_options(params)
            if img_opts:
                args.extend(['-i', img_opts])
        elif htpp_mode == HtppMode.MAP:
            map_opts = CommandBuilder._build_map_options(params)
            if map_opts:
                args.extend(['-m', map_opts])

        # 输出文件 (-o)
        if params.output_file:
            args.extend(['-o', params.output_file])

        # 线程数 (-t)
        if params.threads > 1:
            args.extend(['-t', str(params.threads)])

        # 输入文件（位置参数，放最后）
        args.append(input_file)

        return args

    # ─── IR 渲染参数 ─────────────────────────────────────────────

    @staticmethod
    def _build_ir_args(cam: dict) -> List[str]:
        """从相机快照构建 -R 参数。"""
        pos = cam["position"]
        tgt = cam["target"]
        up = cam["up"]
        fov = cam["fov"]
        spp = cam["spp"]
        w, h = cam["resolution"]

        r_val = (
            f"spp={spp}"
            f":img={w}x{h}"
            f":fov={fov}"
            f":pos={pos[0]},{pos[1]},{pos[2]}"
            f":tgt={tgt[0]},{tgt[1]},{tgt[2]}"
            f":up={up[0]},{up[1]},{up[2]}"
        )
        return ['-R', r_val]

    # ─── 探针参数 ────────────────────────────────────────────────

    @staticmethod
    def _build_probe_args(probes: List[dict]) -> List[str]:
        """从探针快照列表构建 -p/-P/-f 参数。"""
        args = []
        for p in probes:
            pos = p["position"]
            ptype = p["probe_type"]
            if ptype == "VOLUME_TEMP":
                time_val = p.get("time")
                if time_val is not None:
                    args.extend(['-p', f'{pos[0]},{pos[1]},{pos[2]},{time_val}'])
                else:
                    args.extend(['-p', f'{pos[0]},{pos[1]},{pos[2]}'])
            elif ptype == "SURFACE_TEMP":
                side = p.get("side", "")
                args.extend(['-P', f'{pos[0]},{pos[1]},{pos[2]}:{side}'])
            elif ptype == "SURFACE_FLUX":
                args.extend(['-f', f'{pos[0]},{pos[1]},{pos[2]}'])
        return args

    # ─── 场求解参数 ──────────────────────────────────────────────

    @staticmethod
    def _build_field_args(fs: FieldSolveConfig) -> List[str]:
        if fs.solve_type == FieldSolveType.MEDIUM_TEMP:
            return ['-m', fs.medium_name]
        elif fs.solve_type == FieldSolveType.SURF_MEAN_TEMP:
            return ['-s', fs.solve_file]
        elif fs.solve_type == FieldSolveType.SURF_TEMP_MAP:
            return ['-S', fs.solve_file]
        elif fs.solve_type == FieldSolveType.SURF_FLUX:
            return ['-F', fs.solve_file]
        return []

    # ─── 高级选项 ────────────────────────────────────────────────

    @staticmethod
    def _build_advanced_args(adv: AdvancedOptions) -> List[str]:
        args = []
        if adv.diff_algorithm:
            args.extend(['-a', adv.diff_algorithm])
        if adv.picard_order > 1:
            args.extend(['-o', str(adv.picard_order)])
        if adv.initial_time > 0:
            args.extend(['-I', str(adv.initial_time)])
        if adv.disable_intrad:
            args.append('-i')
        if adv.extended_results:
            args.append('-e')
        if adv.rng_state_in:
            args.extend(['-x', adv.rng_state_in])
        if adv.rng_state_out:
            args.extend(['-X', adv.rng_state_out])
        return args

    # ─── HTPP 选项 ───────────────────────────────────────────────

    @staticmethod
    def _build_image_options(params: HtppParams) -> str:
        """Only non-default image options; empty string means all defaults."""
        parts = []
        if params.exposure != 1.0:
            parts.append(f'exposure={params.exposure}')
        if params.white_scale is not None:
            parts.append(f'white={params.white_scale}')
        return ':'.join(parts)

    @staticmethod
    def _build_map_options(params: HtppParams) -> str:
        """Only non-default map options; empty string means all defaults."""
        parts = []
        if params.pixel_component != 0:
            parts.append(f'pixcpnt={params.pixel_component}')
        if params.palette:
            parts.append(f'palette={params.palette}')
        if params.range_min is not None and params.range_max is not None:
            parts.append(f'range={params.range_min},{params.range_max}')
        if params.gnuplot:
            parts.append('gnuplot')
        return ':'.join(parts)

    # ─── IR 输出文件名 ──────────────────────────────────────────

    @staticmethod
    def build_ir_output_filename(camera_snapshot: dict) -> str:
        w, h = camera_snapshot["resolution"]
        spp = camera_snapshot["spp"]
        return f"IRR_{w}x{h}x{spp}.ht"
