import numpy as np
import cv2
import math
import file_utils

def getDetBoxes_core(textmap, linkmap, text_threshold, link_threshold, low_text, s=True):
    # prepare data
    linkmap = linkmap.copy()
    textmap = textmap.copy()
    img_h, img_w = textmap.shape

    """ labeling method """
    # 二值化
    ret, text_score = cv2.threshold(textmap, low_text, 1, 0)
    ret, link_score = cv2.threshold(linkmap, link_threshold, 1, 0)
    ret, text_score1 = cv2.threshold(textmap, low_text, 255, 0)
    ret, link_score1 = cv2.threshold(linkmap, link_threshold, 255, 0)
    cv2.imwrite('result/bi_text_map.jpg', text_score1)
    cv2.imwrite('result/bi_link_score.jpg', link_score1)

    # 小于0的置0，大于1的置1，[0， 1]之间的保留原始数据
    if s:
        text_score_comb = np.clip(text_score + link_score, 0, 1)
    else:
        text_score_comb = np.clip(text_score, 0, 1)
    # 连通域检测
    nLabels, labels, stats, centroids = cv2.connectedComponentsWithStats(text_score_comb.astype(np.uint8), connectivity=4)

    det = []
    mapper = []
    for k in range(1, nLabels):
        # size filtering
        # 取面积
        size = stats[k, cv2.CC_STAT_AREA]

        if size < 10: continue

        # thresholding
        # 抑制概率低于 text_threshold 的点
        if np.max(textmap[labels==k]) < text_threshold: continue

        # make segmentation map
        segmap = np.zeros(textmap.shape, dtype=np.uint8)
        segmap[labels==k] = 255
        segmap[np.logical_and(link_score==1, text_score==0)] = 0   # remove link area
        x, y = stats[k, cv2.CC_STAT_LEFT], stats[k, cv2.CC_STAT_TOP]
        w, h = stats[k, cv2.CC_STAT_WIDTH], stats[k, cv2.CC_STAT_HEIGHT]
        niter = int(math.sqrt(size * min(w, h) / (w * h)) * 2)
        sx, ex, sy, ey = x - niter, x + w + niter + 1, y - niter, y + h + niter + 1
        # boundary check
        if sx < 0 : sx = 0
        if sy < 0 : sy = 0
        if ex >= img_w: ex = img_w
        if ey >= img_h: ey = img_h
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(1 + niter, 1 + niter))
        segmap[sy:ey, sx:ex] = cv2.dilate(segmap[sy:ey, sx:ex], kernel)

        # make box
        np_contours = np.roll(np.array(np.where(segmap!=0)),1,axis=0).transpose().reshape(-1,2)
        rectangle = cv2.minAreaRect(np_contours)
        box = cv2.boxPoints(rectangle)

        # align diamond-shape
        w, h = np.linalg.norm(box[0] - box[1]), np.linalg.norm(box[1] - box[2])
        box_ratio = max(w, h) / (min(w, h) + 1e-5)
        if abs(1 - box_ratio) <= 0.1:
            l, r = min(np_contours[:,0]), max(np_contours[:,0])
            t, b = min(np_contours[:,1]), max(np_contours[:,1])
            box = np.array([[l, t], [r, t], [r, b], [l, b]], dtype=np.float32)

        # make clock-wise order
        startidx = box.sum(axis=1).argmin()
        box = np.roll(box, 4-startidx, 0)
        box = np.array(box)

        det.append(box)
        mapper.append(k)

    return det, labels, mapper


def getDetBoxes(textmap, linkmap, text_threshold, link_threshold, low_text, s=True):
    boxes, labels, mapper = getDetBoxes_core(textmap, linkmap, text_threshold, link_threshold, low_text, s)

    return boxes


def adjustResultCoordinates(polys, ratio_w, ratio_h, ratio_net = 2):
    if len(polys) > 0:
        polys = np.array(polys)
        for k in range(len(polys)):
            if polys[k] is not None:
                polys[k] *= (ratio_w * ratio_net, ratio_h * ratio_net)
    return polys

def get_result_img(image, score_text, score_link, text_threshold=0.68, link_threshold=0.4, low_text=0.08, ratio_w=1.0, ratio_h=1.0):
    boxes = getDetBoxes(score_text, score_link, text_threshold, link_threshold, low_text, s=False)
    boxes = adjustResultCoordinates(boxes, ratio_w, ratio_h)
    file_utils.saveResult('/content/CRAFT-tensorflow/outputs/text_image_char.jpg', image, boxes, dirname='/home/user4/ysx/text_image/')
    boxes = getDetBoxes(score_text, score_link, text_threshold, link_threshold, low_text, s=True)
    boxes = adjustResultCoordinates(boxes, ratio_w, ratio_h)
    file_utils.saveResult('/content/CRAFT-tensorflow/outputs/text_image_word.jpg', image, boxes, dirname='/home/user4/ysx/text_image/')