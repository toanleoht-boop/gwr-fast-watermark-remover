import os, shutil, subprocess, tempfile
import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}


class WatermarkWorker(QThread):
    finished = pyqtSignal(int, int)
    progress = pyqtSignal(int, int, str)
    error = pyqtSignal(str)

    def __init__(self, input_paths, output_dir=None, mode='smart', roi_params=None):
        super().__init__()
        self.input_paths, self.output_dir = list(input_paths), output_dir
        self.roi_params = roi_params or (77.5, 86.8, 13.0, 8.5)
        self._cancelled = False

    def cancel(self): self._cancelled = True

    def run(self):
        succeeded = failed = 0
        total = len(self.input_paths)
        for index, source in enumerate(self.input_paths, 1):
            if self._cancelled: break
            try:
                destination = self.output_dir or os.path.join(os.path.dirname(os.path.dirname(source)), 'Template')
                os.makedirs(destination, exist_ok=True)
                output = os.path.join(destination, os.path.basename(source))
                if os.path.abspath(output) == os.path.abspath(source):
                    raise ValueError('Thư mục đầu ra không được trùng thư mục nguồn.')
                self.progress.emit(index-1, total, f'Đang xử lý {os.path.basename(source)}')
                if os.path.splitext(source)[1].lower() in VIDEO_EXTS:
                    self._video(source, output, index-1, total)
                else:
                    self._image(source, output)
                succeeded += 1
            except Exception as exc:
                failed += 1
                self.error.emit(f'{os.path.basename(source)}: {exc}')
        self.progress.emit(succeeded+failed, total, 'Hoàn tất')
        self.finished.emit(succeeded, failed)

    @staticmethod
    def _roi(shape, values):
        h, w = shape[:2]
        x, y = max(0, min(int(values[0]*w/100), w-1)), max(0, min(int(values[1]*h/100), h-1))
        rw, rh = max(2, min(int(values[2]*w/100), w-x)), max(2, min(int(values[3]*h/100), h-y))
        return x, y, rw, rh

    @staticmethod
    def smart_remove(image, x, y, rw, rh):
        h, w = image.shape[:2]
        gap = max(4, min(rw, rh)//10)
        options = [(sx, sy) for sx, sy in ((x-rw-gap,y),(x+rw+gap,y),(x,y-rh-gap),(x,y+rh+gap))
                   if sx >= 0 and sy >= 0 and sx+rw <= w and sy+rh <= h]
        if not options:
            mask = np.zeros((h,w), np.uint8); mask[y:y+rh,x:x+rw] = 255
            return cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        border = max(2, min(6, min(rw,rh)//6))
        target = image[y:y+rh,x:x+rw].astype(np.float32)
        edge = np.zeros((rh,rw), bool); edge[:border]=edge[-border:]=True; edge[:,:border]=edge[:,-border:]=True
        sx, sy = min(options, key=lambda p: float(np.mean((image[p[1]:p[1]+rh,p[0]:p[0]+rw].astype(np.float32)[edge]-target[edge])**2)))
        source = image[sy:sy+rh,sx:sx+rw].copy()
        mask = np.full((rh,rw),255,np.uint8)
        feather = max(3,min(10,min(rw,rh)//8)); ramp=np.linspace(0,255,feather,dtype=np.uint8)
        mask[:feather]=np.minimum(mask[:feather],ramp[:,None]); mask[-feather:]=np.minimum(mask[-feather:],ramp[::-1,None])
        mask[:,:feather]=np.minimum(mask[:,:feather],ramp[None,:]); mask[:,-feather:]=np.minimum(mask[:,-feather:],ramp[None,::-1])
        try: return cv2.seamlessClone(source,image,mask,(x+rw//2,y+rh//2),cv2.NORMAL_CLONE)
        except cv2.error:
            full=np.zeros((h,w),np.uint8); full[y:y+rh,x:x+rw]=255
            return cv2.inpaint(image,full,3,cv2.INPAINT_TELEA)

    def _image(self, source, output):
        image=cv2.imdecode(np.fromfile(source,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None: raise ValueError('Không đọc được ảnh.')
        result=self.smart_remove(image,*self._roi(image.shape,self.roi_params))
        ok,data=cv2.imencode(os.path.splitext(output)[1] or '.png',result)
        if not ok: raise ValueError('Không ghi được ảnh đầu ra.')
        data.tofile(output)

    def _video(self, source, output, file_index, total):
        temp=tempfile.mkdtemp(prefix='gwr_'); cap=writer=None
        try:
            local=os.path.join(temp,'input'+(os.path.splitext(source)[1] or '.mp4')); raw=os.path.join(temp,'video.mp4')
            shutil.copy2(source,local); cap=cv2.VideoCapture(local)
            if not cap.isOpened(): raise ValueError('Không mở được video.')
            w,h=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps=cap.get(cv2.CAP_PROP_FPS) or 30; frames=max(1,int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            writer=cv2.VideoWriter(raw,cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
            if not writer.isOpened(): raise ValueError('Không tạo được video đầu ra.')
            roi=self._roi((h,w),self.roi_params); done=0
            while not self._cancelled:
                ok,frame=cap.read()
                if not ok: break
                writer.write(self.smart_remove(frame,*roi)); done+=1
                if done%12==0: self.progress.emit(file_index,total,f'{os.path.basename(source)} · {int(done*100/frames)}%')
            cap.release(); cap=None; writer.release(); writer=None
            if not self._cancelled: self._mux(raw,local,output)
        finally:
            if cap is not None: cap.release()
            if writer is not None: writer.release()
            shutil.rmtree(temp,ignore_errors=True)

    @staticmethod
    def _mux(video, original, output):
        if imageio_ffmpeg is None: shutil.copy2(video,output); return
        cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-i',video,'-i',original,
             '-map','0:v:0','-map','1:a?','-c:v','copy','-c:a','copy','-shortest','-movflags','+faststart',output]
        result=subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode or not os.path.exists(output): raise ValueError('FFmpeg: '+result.stderr[-250:])
