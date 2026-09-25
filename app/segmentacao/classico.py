import numpy as np
import cv2
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from skimage.measure import regionprops

class CoffeeSegmentationPipeline:
    def __init__(self, min_grain_area=100, aspect_ratio_threshold=2.0):
        self.min_grain_area = min_grain_area
        self.aspect_ratio_threshold = aspect_ratio_threshold
    
    def remove_nao_ROI(self, img):
        """Remove background baseado em HSV Hue"""
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        hue = hsv[:,:,0]
        mask = np.uint8(hue <= 60) * 255
        
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            max_idx = 1 + np.argmax(areas)
            mask_largest = np.zeros_like(mask)
            mask_largest[labels == max_idx] = 255
        else:
            mask_largest = mask.copy()
        
        return mask_largest
    
    def limpa_e_preenche_buraco(self, img_thresh, mask_largest, limiar=1000):
        """Limpa ruídos e preenche buracos"""
        inv = cv2.bitwise_not(img_thresh)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        inv_clean = cv2.morphologyEx(inv, cv2.MORPH_OPEN, kernel)
        
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv_clean, connectivity=8)
        
        mask = np.zeros_like(inv_clean)
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            aspect_ratio = max(w, h) / (min(w, h) + 1e-5)
            if area > 100 and aspect_ratio < 2:
                mask[labels == i] = 255
        
        mask_dilated = cv2.dilate(mask, kernel, iterations=1)
        inv_final = cv2.bitwise_not(mask_dilated)
        img_cut = cv2.bitwise_and(mask_largest, mask_largest, mask=inv_final)
        
        contornos, _ = cv2.findContours(img_cut, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for con in contornos:
            if cv2.contourArea(con) < limiar:
                cv2.drawContours(img_cut, [con], -1, 255, -1)
        
        return img_cut
    
    def segmentacao_watershed(self, img_rgb):
        """Pipeline de segmentação completo"""
        # Pré-processamento
        mask_largest = self.remove_nao_ROI(img_rgb.copy())
        
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        V = hsv[:, :, 2].astype(np.float32)
        gray1 = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        
        gray = cv2.normalize(V + gray1, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        gray = cv2.GaussianBlur(gray, (5, 9), sigmaX=2)
        
        # Limiarização adaptativa
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Preenchimento de buracos
        thresh = self.limpa_e_preenche_buraco(thresh, mask_largest, 1000)
        
        # Transformada de distância
        dist = ndi.distance_transform_edt(thresh)
        
        # Picos locais
        coordinates = peak_local_max(dist, min_distance=20, labels=thresh)
        local_max = np.zeros_like(dist, dtype=bool)
        local_max[tuple(coordinates.T)] = True
        
        # Marcadores e watershed
        markers = ndi.label(local_max, structure=np.ones((3, 3)))[0]
        labels = watershed(-dist, markers, mask=thresh)
        
        return labels, img_rgb
    
    def extrair_segmentos(self, img_rgb, labels):
        """Extrai segmentos individuais com filtragem por IQR"""
        segmentos = []
        areas = []
        
        for label in np.unique(labels):
            if label == 0:
                continue
            mascara = np.zeros(labels.shape, dtype='uint8')
            mascara[labels == label] = 255
            cnts = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
            if len(cnts) == 0:
                continue
            c = max(cnts, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(c)
            seg = img_rgb[y:y+h, x:x+w]
            segmentos.append(seg)
            areas.append(w * h)
        
        # Filtro por IQR
        if len(areas) == 0:
            return [], [], []
            
        areas_np = np.array(areas)
        Q1 = np.percentile(areas_np, 25)
        Q3 = np.percentile(areas_np, 75)
        IQR = Q3 - Q1
        limite_inferior = Q1 - 1.5 * IQR
        limite_superior = Q3 + 1.5 * IQR
        
        indices_filtrados = [i for i, a in enumerate(areas_np) 
                            if limite_inferior <= a <= limite_superior]
        
        segmentos_filtrados = [segmentos[i] for i in indices_filtrados]
        areas_filtradas = [areas[i] for i in indices_filtrados]
        
        return segmentos_filtrados, areas_filtradas, indices_filtrados
    
    def centralizar_segmentos(self, segmentos):
        """Centraliza segmentos em quadrado de referência"""
        if not segmentos:
            return []
        
        areas = [seg.shape[0] * seg.shape[1] for seg in segmentos]
        idx_maior = np.argmax(areas)
        h_maior, w_maior = segmentos[idx_maior].shape[:2]
        lado_ref = max(h_maior, w_maior)
        
        imagens_centralizadas = []
        for seg in segmentos:
            h, w = seg.shape[:2]
            escala = min(lado_ref / h, lado_ref / w, 1.0)
            
            if escala < 1.0:
                new_w, new_h = int(w * escala), int(h * escala)
                seg = cv2.resize(seg, (new_w, new_h), interpolation=cv2.INTER_AREA)
                h, w = seg.shape[:2]
            
            base = np.zeros((lado_ref, lado_ref, 3), dtype=np.uint8)
            y_offset = max((lado_ref - h) // 2, 0)
            x_offset = max((lado_ref - w) // 2, 0)
            
            y_end = min(y_offset + h, lado_ref)
            x_end = min(x_offset + w, lado_ref)
            seg = seg[:y_end - y_offset, :x_end - x_offset]
            
            base[y_offset:y_end, x_offset:x_end] = seg
            imagens_centralizadas.append(base)
        
        return imagens_centralizadas
    
    def processar_imagem(self, caminho_imagem):
        """Pipeline completo"""
        img_bgr = cv2.imread(caminho_imagem)
        if img_bgr is None:
            raise ValueError(f"Não foi possível ler a imagem: {caminho_imagem}")
        
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        
        labels, img_original = self.segmentacao_watershed(img_rgb)
        segmentos, areas, indices = self.extrair_segmentos(img_rgb, labels)
        segmentos_centralizados = self.centralizar_segmentos(segmentos)
        
        return {
            'labels': labels,
            'img_original': img_original,
            'segmentos': segmentos_centralizados,
            'areas': areas,
            'indices_originais': indices,
            'num_segmentos': len(segmentos_centralizados)
        }