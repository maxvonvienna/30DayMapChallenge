import bpy
import numpy as np
import sys
from pathlib import Path
from mathutils import Vector

args = sys.argv[sys.argv.index('--')+1:]
source, output = map(lambda x: Path(x).resolve(), args[:2])
exaggeration = float(args[2]) if len(args)>2 else 2.0
with np.load(source) as d:
    z, dx, dy = d['z'], float(d['dx']), float(d['dy'])
valid = np.isfinite(z)
if not valid.any():
    raise ValueError('DEM has no valid elevations')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
rows, cols = z.shape
scale = 100 / max(cols*dx, rows*dy)
r,c = np.where(valid)
idx = np.full(z.shape,-1,dtype=np.int32)
idx[r,c] = np.arange(len(r))
verts = np.column_stack(((c-(cols-1)/2)*dx*scale, ((rows-1)/2-r)*dy*scale, z[r,c]*scale*exaggeration)).tolist()
a,b,e,f = idx[:-1,:-1],idx[:-1,1:],idx[1:,1:],idx[1:,:-1]
ok = (a>=0)&(b>=0)&(e>=0)&(f>=0)
faces = np.column_stack((a[ok],f[ok],e[ok],b[ok])).tolist()
if not faces: raise ValueError('No valid terrain faces')
mesh=bpy.data.meshes.new('DEM'); mesh.from_pydata(verts,[],faces); mesh.update()
obj=bpy.data.objects.new('Austria',mesh); bpy.context.collection.objects.link(obj)
mesh.polygons.foreach_set('use_smooth',np.ones(len(faces),dtype=bool))
mat=bpy.data.materials.new('Ivory'); mat.diffuse_color=(0.82,0.78,0.68,1); obj.data.materials.append(mat)
solid=obj.modifiers.new('Relief thickness','SOLIDIFY'); solid.thickness=0.25
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=48; scene.cycles.use_denoising=True
scene.world=bpy.data.worlds.new('Studio'); scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(0.12,0.12,0.12,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=0.35

def aim(o,target): o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()

def area(name,location,power,size):
    bpy.ops.object.light_add(type='AREA',location=location); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; aim(o,(0,0,0))
area('Northwest key',(-55,65,75),180000,28)
area('Fill',(45,-30,65),45000,65)
bpy.ops.mesh.primitive_plane_add(size=350,location=(0,0,float(np.nanmin(z))*scale*exaggeration-0.6))
floor=bpy.context.object; m=bpy.data.materials.new('Charcoal'); m.diffuse_color=(0.025,0.032,0.045,1); floor.data.materials.append(m)
bpy.ops.object.camera_add(location=(0,-85,150)); cam=bpy.context.object; aim(cam,(0,0,0)); cam.data.type='ORTHO'; cam.data.ortho_scale=115; scene.camera=cam
scene.render.resolution_x=3000; scene.render.resolution_y=2000; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(output)
output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output.with_suffix('.blend')))
bpy.ops.render.render(write_still=True)
