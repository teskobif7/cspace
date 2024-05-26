import dataclasses
import torch


def qua_to_rpy(qua):
    qx, qy, qz, qw = torch.unbind(qua, dim=-1)

    t0 = +2.0 * (qw * qx + qy * qz)
    t1 = +1.0 - 2.0 * (qx * qx + qy * qy)
    r = torch.atan2(t0, t1)

    t2 = +2.0 * (qw * qy - qz * qx)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    p = torch.asin(t2)

    t3 = +2.0 * (qw * qz + qx * qy)
    t4 = +1.0 - 2.0 * (qy * qy + qz * qz)
    y = torch.atan2(t3, t4)

    return torch.stack((r, p, y), dim=-1)


def rpy_to_qua(rpy):
    r, p, y = torch.unbind(rpy, dim=-1)

    sin_r_2, cos_r_2 = torch.sin(r / 2.0), torch.cos(r / 2.0)
    sin_p_2, cos_p_2 = torch.sin(p / 2.0), torch.cos(p / 2.0)
    sin_y_2, cos_y_2 = torch.sin(y / 2.0), torch.cos(y / 2.0)

    qx = sin_r_2 * cos_p_2 * cos_y_2 - cos_r_2 * sin_p_2 * sin_y_2
    qy = cos_r_2 * sin_p_2 * cos_y_2 + sin_r_2 * cos_p_2 * sin_y_2
    qz = cos_r_2 * cos_p_2 * sin_y_2 - sin_r_2 * sin_p_2 * cos_y_2
    qw = cos_r_2 * cos_p_2 * cos_y_2 + sin_r_2 * sin_p_2 * sin_y_2

    return torch.stack((qx, qy, qz, qw), dim=-1)


@dataclasses.dataclass(frozen=True, kw_only=True)
class Transform:
    xyz: torch.Tensor
    qua: torch.Tensor

    @property
    def rpy(self):
        return qua_to_rpy(self.qua)


class Joint(torch.nn.Module):
    def __init__(self, spec):
        super().__init__()
        self.spec = spec

    def forward(self, data):
        shape = data.unsqueeze(-1).shape

        xyz = torch.as_tensor(
            self.spec.origin.xyz,
            device=data.device,
        )
        rpy = torch.as_tensor(
            self.spec.origin.rpy,
            device=data.device,
        )
        qua = rpy_to_qua(rpy)

        return Transform(xyz=xyz.repeat(*shape), qua=qua.repeat(*shape))
