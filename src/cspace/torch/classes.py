import cspace.cspace.classes
import cspace.torch.ops
import dataclasses
import functools
import operator
import torch


@dataclasses.dataclass(frozen=True, kw_only=True)
class Transform(cspace.cspace.classes.Transform):
    @property
    def rpy(self):
        return cspace.torch.ops.rot_to_rpy(self.rot)

    @property
    def qua(self):
        return cspace.torch.ops.rot_to_qua(self.rot)

    def inverse(self):
        assert self.rot.ndim == 2 and other.rot.ndim == 2
        xyz = torch.mm(self.rot.transpose(), self.xyz)
        rot = self.rot.transpose()
        return Transform(xyz=xyz, rot=rot)

    def __mul__(self, other):
        assert self.rot.ndim == 2 and other.rot.ndim == 2
        xyz = torch.mm(self.rot, other.xyz.unsqueeze(-1)).squeeze(-1) + self.xyz
        rot = torch.mm(self.rot, other.rot)
        return Transform(xyz=xyz, rot=rot)


class JointOp(cspace.cspace.classes.JointOp):
    def origin(self, data, xyz, rpy):
        data = torch.as_tensor(data, dtype=torch.float64)

        xyz = torch.as_tensor(
            xyz,
            device=data.device,
            dtype=data.dtype,
        )
        rpy = torch.as_tensor(
            rpy,
            device=data.device,
            dtype=data.dtype,
        )
        rot = cspace.torch.ops.rpy_to_rot(rpy)

        return Transform(xyz=xyz, rot=rot)

    def linear(self, data, axis, upper, lower):
        data = torch.as_tensor(data, dtype=torch.float64)
        data = data.unsqueeze(-1)
        shape = data.shape

        data = torch.clip(data, min=lower, max=upper)
        axis = torch.as_tensor(
            axis,
            device=data.device,
            dtype=data.dtype,
        )
        xyz = torch.multiply(data, axis)
        rot = torch.eye(
            3,
            device=data.device,
            dtype=data.dtype,
        ).expand(*(shape[:-2] + tuple([-1, -1])))
        return Transform(xyz=xyz, rot=rot)

    def angular(self, data, axis, upper, lower):
        data = torch.as_tensor(data, dtype=torch.float64)
        data = data.unsqueeze(-1)
        shape = data.shape

        xyz = torch.as_tensor(
            (0.0, 0.0, 0.0),
            device=data.device,
            dtype=data.dtype,
        ).expand(*(shape[:-1] + tuple([-1])))
        data = (
            torch.clip(data, min=lower, max=upper)
            if (upper is not None or lower is not None)
            else data
        )
        axis = torch.as_tensor(
            axis,
            device=data.device,
            dtype=data.dtype,
        )
        rpy = torch.multiply(data, axis)
        rot = cspace.torch.ops.rpy_to_rot(rpy)
        return Transform(xyz=xyz, rot=rot)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Spec(cspace.cspace.classes.Spec):
    def __post_init__(self):
        super().__post_init__()

        def f_link(spec, data, link, base=None):
            def f_transform(spec, data, name, forward):
                index = spec.joint.index(name)
                value = torch.select(data, dim=-1, index=index)
                transform = spec.joint(name).transform(value)

                transform = transform if forward else transform.inverse()

                return transform

            transform = functools.reduce(
                operator.mul,
                [
                    f_transform(spec, data, name, forward)
                    for name, forward in reversed(spec.route(link, base))
                ],
                Transform(
                    xyz=torch.as_tensor(
                        [0, 0, 0], device=data.device, dtype=torch.float64
                    ),
                    rot=torch.eye(3, device=data.device, dtype=torch.float64),
                ),
            )
            return torch.concatenate((transform.xyz, transform.qua), dim=-1)

        def f_spec(spec, data, *link, base=None):
            data = torch.as_tensor(data, dtype=torch.float64)
            assert data.shape[-1] == len(spec.joint)
            base = base if base else self.base

            return torch.stack(
                tuple(f_link(spec, data, item, base=base).data for item in link), dim=-2
            )

        for joint in self.joint:
            object.__setattr__(joint, "op", JointOp())
        object.__setattr__(self, "function", f_spec)
