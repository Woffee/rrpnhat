"""
Version 3，暂时不考虑迭代，假设分类已知，写一篇段文章出来
"""

import pandas as pd
import multiprocessing
import numpy as np

from numba import jit
import csv
import math
import datetime
import time
import scipy
import os
import math
from scipy.optimize import nnls
from scipy.stats import chi
import random
from clean_data import Clean_data
import logging

# calculate error in 1.5
def get_min_error(E1, E2, n, k, t):
    df = (n*k)**2
    tmp = (np.std(E1, dtype=np.float64) + np.std(E2,dtype=np.float64)) * 0.5
    error = tmp**2 * chi.ppf(0.9, df) / t
    return error


def is_constrained(E1, E2, min_error):
    e = (np.sum( (E1-E2) ** 2 ))
    print("real_error:",e)
    return e < min_error


def constrained_clustering(C):
    return C


@jit
def gaussiankernel(x, z, args, N):
    if N == 1:
        sigma = args
        y = (1. / math.sqrt(2. * math.pi) / sigma) * math.exp(-(x - z) ** 2 / (2. * sigma ** 2))
    else:
        sigma = args
        cov = []
        for j in range(N):
            cov += [1. / sigma[j, j] ** 2]
        N = float(N)

        y = 1. / (2. * math.pi) ** (N / 2.) * abs(np.linalg.det(sigma)) ** (-1.) * math.exp(
            (-1. / 2.) * np.dot((x - z) ** 2, np.array(cov)))
    return y


def lasso(x,D,y):
    temp = (np.dot(D,x))/D.shape[1] - y
    eq = np.dot(temp,temp)
    return eq+np.dot(x,x)


def lessObsUpConstrain(x,D,y):
    # print("x.shape:",x.shape)
    # print("D.shape:",D.shape)
    # print("y.shape:",y.shape)
    temp = (np.dot(D,x))/D.shape[1] - y
    eq = np.dot(temp,temp)
    return -eq+0.1


def moreObsfunc(x,D,y):
    temp = y.reshape(len(y),1)-np.dot(D,x.reshape(len(x),1))
    temp = temp.reshape(1,len(temp))
    return np.asscalar(np.dot(temp,temp.T))


def square_sum(x):
    # y = np.dot(x,x)
    y = np.sum( x**2 )
    return y

# 1.4
def minimizer_L1(x):
    D=x[1]
    y=x[0].T
    print('D>>>>>>>>>>>>>>>>>>>>>>')
    print(D)
    print('y>>>>>>>>>>>>>>>>>>>>>>')
    print(y)
    # x0=x[2].reshape(D.shape[1],)-(random.rand(D.shape[1]))/100
    x0=np.ones(D.shape[1],)
    # print('guess x0>>>>>>>>>>')
    # print(x0)
    print("D:", D.shape)
    # D: (15, 120)
    if(D.shape[0] < D.shape[1]):
        #less observations than nodes
        upcons = {'type':'ineq','fun':lessObsUpConstrain,'args':(D,y)}
        result = scipy.optimize.minimize(square_sum, x0, args=(), method='SLSQP', jac=None, bounds=scipy.optimize.Bounds(0,1), constraints=[upcons], tol=None, callback=None, options={'maxiter': 100, 'ftol': 1e-03, 'iprint': 1, 'disp': False, 'eps': 1.4901161193847656e-08})
        print(result)
    else:
        result = scipy.optimize.minimize(moreObsfunc, x0, args=(D,y), method='L-BFGS-B', jac=None, bounds=scipy.optimize.Bounds(0,1), tol=None, callback=None, options={'disp': None, 'maxcor': 10, 'ftol': 2.220446049250313e-09, 'gtol': 1e-05, 'eps': 1e-08, 'maxfun': 15000, 'maxiter': 15000, 'iprint': -1, 'maxls': 20})
        print(result)
    return result.x


def read_data(filepath, K, days, sample_size = 100):
    # reading input data
    # data contains:feature vector, state
    data = pd.read_csv(filepath, encoding='utf-8')
    data = data[:sample_size]

    data.drop('user_id', axis=1, inplace=True)
    data = data.dropna()
    data.index = np.arange(len(data))

    ## get the features of nodes ##
    feature_sample = data[['FOLLOWERS_COUNT', 'FRIENDS_COUNT', 'STATUSES_COUNT', 'lat', 'lon']]
    feature_sample.index = data.index
    # feature_col = feature_sample.columns
    ## rescale features to a compact cube ##
    # feature_max = []
    feature_sample['lon'] += 180
    # print(feature_sample[['lat', 'lon']][:5])
    for item in feature_sample.columns:
        # feature_max.append(max(np.absolute(np.array(feature_sample[item]))))
        feature_sample[item] /= max(np.absolute(np.array(feature_sample[item])))


    ## define infect event and get 0-1 infection status sequence ##

    spreading_key = []
    for k in range(K):
        for d in range(days):
            spreading_key.append('k_' + str(k) + '_d_' + str(d))

    spreading_sample = np.array(data[spreading_key])
    spreading_sample = spreading_sample.reshape((sample_size * K, days))

    # delete t with all zeros
    all_zero_columns = np.where(~spreading_sample.any(axis=0))[0]
    spreading_sample = np.delete(spreading_sample, all_zero_columns, axis=1)

    # delete t which is not updated since last t
    spreading_sample = spreading_sample.T
    index = range(len(spreading_sample))
    deleted = []
    for i in range(len(spreading_sample)):
        if i>0:
            last = spreading_sample[i-1]
            now  = spreading_sample[i]
            if (last==now).all():
                deleted.append(i)
    print("deleted:", deleted)
    exist = list(set(index).difference(set(deleted)))
    # spreading_sample = np.delete(spreading_sample, deleted, axis=0)


    random.shuffle(exist)
    T1 = sorted(exist[0:int(len(exist)/2)])
    T2 = sorted(exist[int(len(exist)/2):])

    print(T1)
    print(T2)
    print("feature_sample:",feature_sample.shape)
    print("spreading_sample:",spreading_sample.shape)


    # np.savetxt(save_path + 'to_file_spreading_sample_all' + rundate + ".txt", spreading_sample)
    # np.savetxt(save_path + 'to_file_spreading_sample_sub' + rundate + ".txt", spreading_sample[T1])

    #
    # # spreading_sample1 = spreading_sample1.reshape((sample_size * K / 2, days))
    # spreading_sample2 = np.array(data[spreading_key2])
    # # spreading_sample2 = spreading_sample2.reshape((sample_size * K / 2, days))
    #

    return feature_sample, spreading_sample, T1, T2

def read_data_from_simulation(obs_filepath, true_net_filepath, K, days, sample_size = 100):
    data = pd.read_csv(true_net_filepath, encoding='utf-8')

    ## get the features of nodes ##
    feature_sample = data[['node1_x', 'node1_y']]
    # real_edge = data[['net_hidden']]

    random.seed(1)
    feature_sample.index = data.index
    ## rescale features to a compact cube ##
    feature_max = []
    for item in feature_sample.columns:
        feature_max.append(max(np.absolute(np.array(feature_sample[item]))))
        feature_sample[item] /= max(np.absolute(np.array(feature_sample[item])))
    ## define infect event and get 0-1 infection status sequence ##

    # draw subsample nodes and spreading info on these nodes
    # data_sample=random.choice(data.index,size=3)
    data_sample = range(0, sample_size)
    features = feature_sample.iloc[list(data_sample)]
    features.index = np.arange(len(data_sample))

    spreading_sample = pd.read_csv(obs_filepath, encoding='utf-8')
    # spreading_sample.drop('user_id', axis=1, inplace=True)
    spreading_sample.drop([spreading_sample.columns[0]], axis=1, inplace=True)
    spreading = spreading_sample.values

    spreading_sample = np.array(spreading_sample)


    # obs = spreading[::10] # [开始：结束：步长]
    # print(obs.shape) # (101, 600)
    # features_matirx = features.values

    index = range(len(spreading_sample))
    deleted = []
    for i in range(len(spreading_sample)):
        if i > 0:
            last = spreading_sample[i - 1]
            now = spreading_sample[i]
            if (last == now).all():
                deleted.append(i)
    print("deleted:", deleted)
    T = list(set(index).difference(set(deleted)))

    # random.shuffle(exist)
    # T1 = sorted(exist[0:int(len(exist) / 2)])
    # T2 = sorted(exist[int(len(exist) / 2):])

    print("features_matirx:",features.shape)
    print("spreading_sample:",spreading_sample.shape)
    return features, spreading_sample, T


# 1.1 & 1.3
def get_r_xit(x, i, t_l, features, spreading, K, T, bandwidth, dt):
    numerator = 0.0
    denominator = 0.0
    # print(features.shape)
    for j in range(features.shape[0]):
        x_j = features.iloc[j]
        g = gaussiankernel(x, x_j, bandwidth, features.shape[1])
        # print("j,t_l,j*K+i:",j,t_l,j*K+i)
        tmp = spreading[t_l+1][j*K+i] - spreading[t_l][j*K+i]
        # if tmp>0:
        #     print("1.0*g*tmp",1.0*g*tmp)
        numerator = numerator + (1.0*g*tmp)

        denominator = denominator + (g*(T[t_l+1]-T[t_l]))
        # print("tmp:",tmp)
        # print("T[t_l+1]:", T[t_l+1])
    # print("numerator", numerator)
    # if numerator == 0.0:
    #     print("00.00")
    #     print("x:", x)
    #     print("i:", i)
    #     print("t_l:", t_l)
    #     print("T[t_l]:", T[t_l])
    #     print(spreading[t_l])
    #     print(spreading[t_l+1])
    #     exit(0)
    # print("numerator:", numerator)
    # print("denominator:", denominator)
    return numerator/denominator


def get_r_matrix(features, spreading, T, K=2, dt=0.01):
    # print(features.shape)
    # print(spreading.shape)
    # (60, 5)
    # (120, 16)
    bandwidth = np.diag(np.ones(features.shape[1]) * float(features.shape[0]) ** (-1. / float(features.shape[1] + 1)))

    r_matrix = []
    for x in range(features.shape[0]):
        print("get_r_matrix now x:",x)
        for i in range(K):
            row = []
            for t in range(len(T)-1):
                r_xit = get_r_xit(features.iloc[x], i, t, features, spreading, K, T, bandwidth, dt)
                row.append(r_xit)
            r_matrix.append(row)
            print(row)

    return np.array(r_matrix)


def save_E(E, filepath):
    # print(E1)
    print("E:", len(E), len(E[0]))
    with open(filepath, "w") as f:
        writer = csv.writer(f)
        writer.writerows(E)
    print(filepath)

def clear_zeros(mitrix):
    # delete t with all zeros
    all_zero_columns = np.where(~mitrix.any(axis=0))[0]
    res = np.delete(mitrix, all_zero_columns, axis=1)
    print("clear 0:")
    print(res)

    return res


# 1.1 & 1.4
def get_E(features, spreading, subT, K, dt=0.01):
    r_matrix = get_r_matrix(features, spreading, subT, K, dt)
    print("r_matrix: ", r_matrix.shape)
    logging.info("r_matrix.shape: " + str( r_matrix.shape))

    spreading = spreading[subT, :]
    spreading = np.delete(spreading, -1, axis=0)

    logging.info("features.shape:" + str(features.shape))
    logging.info("spreading.shape:" + str(spreading.shape))
    logging.info("subT:" + str(subT))

    np.savetxt(save_path + 'to_file_spreading_' + rundate + ".txt", spreading)

    np.savetxt(save_path + 'to_file_r_matrix_' + rundate + ".txt", r_matrix)

    cores = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(processes=cores)


    # spreading = np.delete(spreading, -1, axis=0)
    # spreading = clear_zeros(spreading)




    xit_all = []
    for r_xit in r_matrix:
        xit_matrix = []
        xit_matrix.append(r_xit)  # y
        xit_matrix.append(spreading)  # D
        # print("r_xit:",len(r_xit))
        # print("spreading:",spreading.shape)
        # r_xit: 15
        # spreading: (15, 120)
        xit_all.append(xit_matrix)
    edge_list = pool.map(minimizer_L1, xit_all)

    return np.array(edge_list)

if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    save_path = BASE_DIR + '/data/'
    rundate = time.strftime("%m%d%H%M", time.localtime())
    # to_file = save_path + "to_file_" + rundate + ".csv"
    today = time.strftime("%Y-%m-%d", time.localtime())
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(filename)s line: %(lineno)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename=BASE_DIR + '/log/' + today + '.log')

    K = 2
    dt = 0.05
    days = 32
    sample_size = 100

    obs_filepath = save_path+'/simulation/obs_1000x300.csv'
    true_net_filepath = save_path+'/simulation/true_net_1000x300.csv'
    feature_sample, spreading_sample, T1 = read_data_from_simulation(obs_filepath, true_net_filepath, K, days, sample_size=100)

    logging.info("start")
    E = get_E(feature_sample, spreading_sample, T1, K, dt)
    save_E(E, save_path + "to_file_E_" + rundate + ".csv")
    logging.info("done")
