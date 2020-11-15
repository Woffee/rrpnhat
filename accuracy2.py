#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import os
import logging

class accuracy:
    def __init__(self, save_path):
        self.save_path = save_path

    def distance(self, a,b):
        s = 0
        for i in range(len(a)):
            s = s + (a[i] - b[i])**2
        return s

    def find_near(self, obj, all):
        dist = self.distance(obj,all[0])
        near = all[0]
        for line in all:
            d = self.distance(obj,line)
            if d < dist:
                dist = d
                near = line
        return near[0], near[1], near[2], near[3], near[4]

    def cal_accuracy(self, x, x_near):
        near_dot = np.dot(x_near,x_near)
        absdiff = x - x_near
        return (near_dot / (np.dot(absdiff,absdiff) + near_dot))

    def process_data(self, filepath_original, filepath_new, filepath_true_net):
        filepath_result = self.save_path + 'true_net_100_result.csv'
        if os.path.exists(filepath_result):
            return filepath_result

        obs_original = pd.read_csv(filepath_original, encoding='utf-8').dropna()
        obs_new = pd.read_csv(filepath_new, encoding='utf-8').dropna()
        true_net = pd.read_csv(filepath_true_net, encoding='utf-8').dropna()

        sum_1 = np.sum(obs_original.values, axis=0)
        sum_2 = np.sum(obs_new.values, axis=0)

        data_sample = range(0, len(sum_1))
        result = true_net[['node1_x', 'node1_y']]
        result = result.iloc[list(data_sample)]

        result['original'] = sum_1
        result['original'] = result['original'] / 1000

        result['time5'] = sum_2
        result['time5'] = result['time5'] / 1000

        pd.DataFrame(result).to_csv(filepath_result, index=None)
        print(filepath_result)
        return filepath_result

    def select10days(self, original):
        T = original.shape[0]
        index = []
        for t in range(int(T/10)):
            index.append( t * 10 )
        return original[index]

    def get_accuracy1(self, filepath_o, filepath_e, K, num_nodes):
        original = pd.read_csv(filepath_o, encoding='utf-8').dropna().to_numpy()
        estimate = pd.read_csv(filepath_e, encoding='utf-8').dropna().to_numpy()
        print(original.shape)

        original = self.select10days(original)
        estimate = self.select10days(estimate)

        s = 0
        for i in range(num_nodes):
            equal = True
            for j in range(K):
                ii = i*K + j
                col1 = original[:, ii]
                col2 = estimate[:, ii]
                if not (col1 == col2).all():
                    equal = False
                    break
            if equal:
                # print("equal:", i)
                s = s + 1
        print("equal:", s, ",all:",num_nodes)
        return 1.0*s/num_nodes

    def get_data(self, fp_obs, fp_true_net, K, num_nodes):
        true_net = pd.read_csv(fp_true_net, encoding='utf-8').dropna()
        obs      = pd.read_csv(fp_obs, encoding='utf-8').dropna().to_numpy()
        T = len(obs)
        nodes = true_net[['node1_x', 'node1_y']].drop_duplicates().to_numpy()

        data = []
        for i in range(num_nodes):
            node = nodes[i]
            for t in range(T):
                row = [node[0], node[1]]
                for k in range(K):
                    row.append( obs[t, i*K + k] )
                row.append(t)
                # print(row)
                data.append(row)
        return np.array(data)

    def build_acc_file(self, fp_obs_o, fp_obs_e, fp_true_net_o, fp_true_net_e, K, num_nodes, save_path, filepath_o, filepath_e):
        data_o = self.get_data(fp_obs_o, fp_true_net_o, K, num_nodes)
        data_e = self.get_data(fp_obs_e, fp_true_net_e, K, num_nodes)

        # filepath_o = save_path + 'data_original.csv'
        # filepath_e = save_path + 'data_estimate.csv'

        np.savetxt(filepath_o, data_o, delimiter=',')
        np.savetxt(filepath_e, data_e, delimiter=',')

        print("saved to", filepath_o)
        print("saved to", filepath_e)
        return filepath_o, filepath_e

    def get_accuracy2_cpp(self, filepath):
        files = os.listdir(filepath)
        acc = []
        for f in files:
            if 'result_seed' in f:
                fullpath = filepath + "/" + f
                cmd = "tail -n 1 %s" % fullpath
                text = os.popen(cmd).read().strip()
                ac = float(text.split(" ")[-1])
                acc.append(ac)
                print(text)
                logging.info(text)
        return np.mean(acc)


    def get_accuracy2(self, fp_obs_o, fp_obs_e, fp_true_net_o, fp_true_net_e, K, num_nodes, save_path):
        data_o = self.get_data(fp_obs_o, fp_true_net_o, K, num_nodes)
        data_e = self.get_data(fp_obs_e, fp_true_net_e, K, num_nodes)

        # data = pd.read_csv(fp_true_net_o, encoding='utf-8').dropna()
        # nodes = data[['node1_x', 'node1_y']]
        # nodes = nodes.drop_duplicates()

        x_near = []
        y_near = []
        n1_near = []
        n2_near = []
        t_near = []

        for i in range(len(data_o)):
            print(i)
            if (data_o[i] == data_e[i]).all():
                x_near.append(data_o[i, 0])
                y_near.append(data_o[i, 1])
                n1_near.append(data_o[i, 2])
                n2_near.append(data_o[i, 3])
                t_near.append(data_o[i, 4])
            else:
                xnear, ynear, n1near, n2near, tnear = self.find_near(data_e[i], data_o)
                x_near.append(xnear)
                y_near.append(ynear)
                n1_near.append(n1near)
                n2_near.append(n2near)
                t_near.append(tnear)

        # x = nodes[['node1_x']].to_numpy().T.reshape(num_nodes * K, )
        # y = nodes[['node1_y']].to_numpy().T.reshape(num_nodes * K, )

        x  = data_e[:,0]
        y  = data_e[:,1]
        n1 = data_e[:,2]
        n2 = data_e[:,3]
        t  = data_e[:,4]

        x_near = np.asarray(x_near)
        y_near = np.asarray(y_near)
        n1_near = np.asarray(n1_near)
        n2_near = np.asarray(n2_near)
        t_near = np.asarray(t_near)

        accuracy_x  = self.cal_accuracy(x, x_near)
        accuracy_y  = self.cal_accuracy(y, y_near)
        accuracy_n1 = self.cal_accuracy(n1, n1_near)
        accuracy_n2 = self.cal_accuracy(n2, n2_near)
        accuracy_t  = self.cal_accuracy(t, t_near)

        print(accuracy_x)
        print(accuracy_y)
        print(accuracy_n1)
        print(accuracy_n2)
        print(accuracy_t)

        accuracy = (accuracy_x + accuracy_y + accuracy_n1 + accuracy_n2 + accuracy_t) / 5
        return accuracy

    def merge(self, obs):
        obs_2 = []
        for i in range(obs.shape[1]):
            if i % 2 == 0:
                a = obs[:, i]
                b = obs[:, i + 1]
                # print(a)
                # print(b)
                obs_2.append(a + b)
        obs_2 = np.array(obs_2).T
        return obs_2

    def get_accuracy3(self, fp_obs_o, fp_obs_e):
        obs_o = np.loadtxt(fp_obs_o, delimiter=',')
        obs_e = np.loadtxt(fp_obs_e, delimiter=',')

        obs_o = self.merge(obs_o)
        obs_e = self.merge(obs_e)

        print(obs_e.shape)
        ss = 0
        for i in range(obs_o.shape[1]):
            # print(i)
            oo = obs_o[:, i]
            ee = obs_e[:, i]
            mm = oo - ee
            ss = ss + sum(mm ** 2)
        return 1.0 * ss / (obs_o.shape[0] * obs_o.shape[1])



