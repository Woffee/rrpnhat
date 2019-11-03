#!/usr/bin/env python
# coding: utf-8


from pandas import DataFrame, read_csv
# import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import re
import string
import gensim
import pickle
import os
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from sklearn.cluster import KMeans
import logging
import queue

class Clean_data():
    def __init__(self, save_path, K):
        np.random.seed(1)
        self.date_list = [20170811 + i for i in range(21)] + [20170901 + i for i in range(11)]
        self.K = K
        self.save_path = save_path


    # s.translate(None, string.punctuation)
    def remove_pattern(self, input_txt, pattern):
        r = re.findall(pattern, input_txt)
        for i in r:
            input_txt = re.sub(i, '', input_txt)
        return input_txt

    def remove_punctuation(self, input_txt):
        return re.sub(r'[^\w\s]', '', input_txt).lower().strip()

    def read_text(self, text_list):
        i = -1
        for line in text_list:
            i = i + 1
            yield gensim.models.doc2vec.TaggedDocument(gensim.utils.simple_preprocess(line), [i])

    def read_data_from_xls(self, read_path):
        filelist = os.listdir(read_path)
        filelist = [item for item in filelist if item.endswith('.xls')]

        print("reading xls...")
        tweet_num = 0
        for k, item in enumerate(filelist):
            if k == 0:
                data = pd.read_excel(read_path + item)
                print(k, read_path + item)
                # user_id=array(data['FROM_USER'])
                user_info = data.groupby('FROM_USER', as_index=False).first()
                user_info = user_info[['FROM_USER', 'FROM_USER_NAME', 'LOCATION', 'FOLLOWERS_COUNT', 'FRIENDS_COUNT',
                                       'STATUSES_COUNT', 'TIME_ZONE',
                                       'lon', 'lat']]  # 'PLACE_FULLNAME','PLACE_TYPE','CITY',
                user_info.rename(columns={'FROM_USER': 'user_id'}, inplace=True)
                tweet = data[['TWEET_ID', 'CREATED_AT', 'FROM_USER', 'LANGUAGE_', 'TEXT_']]
            else:
                data = pd.read_excel(read_path + item)
                print(k, read_path + item)
                # user_id=append(user_id,array(data['FROM_USER']))
                user_info1 = data.groupby('FROM_USER', as_index=False).first()
                user_info1 = user_info1[['FROM_USER', 'FROM_USER_NAME', 'LOCATION', 'FOLLOWERS_COUNT', 'FRIENDS_COUNT',
                                         'STATUSES_COUNT', 'TIME_ZONE', 'lon',
                                         'lat']]  # 'PLACE_FULLNAME','PLACE_TYPE','CITY',
                user_info1.rename(columns={'FROM_USER': 'user_id'}, inplace=True)
                user_info = pd.concat([user_info, user_info1])
                tweet = pd.concat([tweet, data[['TWEET_ID', 'CREATED_AT', 'FROM_USER', 'LANGUAGE_', 'TEXT_']]])

        tweet.rename(columns={'FROM_USER': 'user_id'}, inplace=True)
        tweet['TWEET_ID'] = tweet['TWEET_ID'].map(lambda x: str(x))
        tweet['CREATED_AT'] = tweet['CREATED_AT'].map(
            lambda x: int(str(x).split('T')[0].split(' ')[0].replace('-', '').replace('/', '')))

        tweet['date_range'] = -1

        tweet['tidy_tweet'] = np.vectorize(self.remove_pattern)(tweet['TEXT_'], "@[\w]*")
        tweet['tidy_tweet'] = np.vectorize(self.remove_pattern)(tweet['tidy_tweet'], "https://t.co/[\w]*")
        tweet['tidy_tweet'] = np.vectorize(self.remove_punctuation)(tweet['tidy_tweet'])

        print("remove empty")
        tweet = tweet[tweet['tidy_tweet'] != '']

        return tweet, user_info


    def tweet2vec(self, tweet):
        train_data = list(self.read_text(tweet['tidy_tweet']))

        print(train_data[:2])

        filepath_doc2vec_model = self.save_path + 'doc2vec_model.bin'
        if os.path.exists(filepath_doc2vec_model):
            print("loading model: ", filepath_doc2vec_model)
            model = Doc2Vec.load(filepath_doc2vec_model)
        else:
            print("training model...")
            model = gensim.models.doc2vec.Doc2Vec(vector_size=50, min_count=2, epochs=40)
            model.build_vocab(train_data)
            # 1 Train model
            model.train(train_data, total_examples=model.corpus_count, epochs=model.epochs)
            # get_ipython().magic(u'time model.train(train_data, total_examples=model.corpus_count, epochs=model.epochs)')
            print("saving model...")
            model.save(filepath_doc2vec_model)

        test_docs = [x.strip().split() for x in tweet['tidy_tweet']]

        # k-means
        print("k means...")
        kmeans_path = self.save_path + "kmeans_model.pkl"


        if os.path.exists(kmeans_path):
            km = pickle.load(open(kmeans_path, "rb"))
        else:
            X = []
            for d in test_docs:
                X.append(model.infer_vector(d))
            km = KMeans(n_clusters= self.K).fit(X)
            pickle.dump(km, open(kmeans_path, "wb"))

        # print("saving text to embeddings...")
        # output_file = self.save_path + "text_embeddings.txt"
        # output = open(output_file, "w")
        i = 0
        vectors = []
        for d in test_docs:
            label = str(km.labels_[i])
            vec = model.infer_vector(d)
            # output.write(label + "," + (" ".join([str(x) for x in vec]) + "\n"))
            vectors.append(vec)
            i = i + 1
        # output.flush()
        # output.close()

        tweet['vector'] = vectors
        tweet['text_label'] = km.labels_
        self.centers = km.cluster_centers_

        print("km.labels:")
        print(km.labels_[0:30])

        return tweet[['user_id','text_label','CREATED_AT','vector']]

    def get_obs(self, vlc):
        for k in range(self.K):
            for d, date in enumerate(self.date_list):
                vlc['k_' + str(k) + '_d_' + str(d)] = 0

        df2 = None
        for k in range(self.K):
            tmp = vlc[vlc['text_label'] == k]
            for d, date in enumerate(self.date_list):
                tmp['k_' + str(k) + '_d_' + str(d)] = 0
                tmp['k_' + str(k) + '_d_' + str(d)][tmp['CREATED_AT'] <= date] = 1
            if k == 0:
                df2 = tmp
            else:
                df2 = pd.concat([df2, tmp])

        key = ['user_id']
        for k in range(self.K):
            for d, date in enumerate(self.date_list):
                key.append('k_' + str(k) + '_d_' + str(d))

        # df2[df2['FROM_USER']=='LuncefordLee'][key]
        # df2.head(20)[key]

        print(len(df2))
        df3 = df2[key].groupby('user_id', as_index=False).agg(sum)

        # delete = []
        # print(df3[ (df3['k_0_d_31']==0) & (df3['k_1_d_31']==0) ])
        # exit(0)

        return df3

    def output(self, tweet, user_info):
        # for k in range(K):
        #     for d,date in enumerate(date_list):
        #         df['k_' + str(k) + '_d_'+str(d)]=0
        #         df[ df['text_label']==k ][ df['CREATED_AT']<=date]['k_' + str(k) + '_d_'+str(d)]=1

        for k in range(self.K):
            for d, date in enumerate(self.date_list):
                tweet['k_' + str(k) + '_d_' + str(d)] = 0

        df2 = None
        for k in range(self.K):
            tmp = tweet[tweet['text_label'] == k]
            for d, date in enumerate(self.date_list):
                tmp['k_' + str(k) + '_d_' + str(d)] = 0
                tmp['k_' + str(k) + '_d_' + str(d)][tmp['CREATED_AT'] <= date] = 1
            if k == 0:
                df2 = tmp
            else:
                df2 = pd.concat([df2, tmp])

        key = ['user_id']
        for k in range(self.K):
            for d, date in enumerate(self.date_list):
                key.append('k_' + str(k) + '_d_' + str(d))

        # df2[df2['FROM_USER']=='LuncefordLee'][key]
        # df2.head(20)[key]

        print(len(df2))
        df3 = df2[key].groupby('user_id', as_index=False).agg(sum)

        user_info = user_info.groupby('user_id', as_index=False).first()
        user_info = pd.merge(user_info, df3, on='user_id', how='inner')

        # print len(df3)
        # user_info.head(20)

        if 'user_id' in key:
            key.remove('user_id')

        print("saving to input.csv...")
        input_data = user_info[['user_id', 'FOLLOWERS_COUNT', 'FRIENDS_COUNT', 'STATUSES_COUNT', 'lat', 'lon'] + key]
        input_data.to_csv(self.save_path + 'input.csv', index=False, encoding='utf-8')

    # =====================================


    # def switching3(self, df, centers, C):
    #     # 计算每个点到中心的距离矩阵
    #     print("Calculating dm...")
    #     dm = np.zeros((len(df), len(centers)), dtype=float)
    #
    #     for i in range(len(df)):
    #         for j in range(len(centers)):
    #             tmp = (df.iloc[i]['vector'] - centers[j]) ** 2
    #             dm[i, j] = tmp.sum()
    #
    #     print("Getting order...")
    #     order = []
    #
    #     for ji in range(self.K):
    #         set_i = df[df['label'] == ji].index
    #         for j in range(self.K):
    #             if j == ji:
    #                 continue
    #             for i in set_i:
    #                 # print(dm[i,j])
    #                 # print(dm[i, ji])
    #                 if dm[i, j] < dm[i, ji]:
    #                     order.append([i, ji, j, dm[i, j]])
    #
    #     print('len of order: ', len(order))
    #     print('Sorting order...')
    #     order.sort(key=lambda x: x[3])
    #
    #     i = 0
    #     for item in order:
    #         origin = item[1]
    #         des = item[2]
    #         id_ = item[0]
    #
    #         print(id_, origin, des)
    #
    #         # if self.fi2(df.iloc[id_]['vector'], centers, origin, des):
    #         #     print('updated')
    #         #     df.set_value(id_, 'label', des)
    #
    #     #         print 'cc=',cc
    #     #         if cc < C[des]:
    #     #             # reset cli = fi()
    #     #             C[des] = cc
    #     #             print 'updated'
    #     #         else:
    #     #             df.set_value(id_,'label', origin)
    #     #             print 'reverted'
    #     return df

    # def update_classification(self, embedding_path, tweet):
    #     labels = []
    #     vectors = []
    #     with open(embedding_path, "r") as file:
    #         i = 0
    #         for line in file:
    #             arr = line.split(',', 1)
    #             label = int(arr[0])
    #             labels.append(label)
    #             vec = list(map(float, arr[1].strip().split(' ')))
    #             vectors.append(vec)
    #
    #     df = pd.DataFrame({
    #         'label': labels,
    #         'vector': vectors
    #     })
    #
    #     df = self.switching3(df, self.centers, [])
    #
    #     tweet['text_label'] = df['label']
    #     return tweet

    def get_vectors(self, n_nodes, mean=0, std=1):
        dim = 50 # dimension of text
        arr = std * np.random.randn(n_nodes, dim) + mean
        mi = np.min(arr)
        ma = np.max(arr)
        for i in range(n_nodes):
            for j in range(dim):
                arr[i][j] = (arr[i][j] - mi) / (ma - mi)
        # print(arr[0])
        # print(np.mean(arr, axis=0))
        # print(np.std(arr, axis=0))
        return arr

    def obs2vlc(self, obs, K, sample_size):
        n_vectors = sum(obs[-1])

        std = [1, 1.2, 1.4]
        mean = [0, 0.1, 0.2]

        vector_queues = []
        for k in range(K):
            q = queue.Queue()
            for vec in self.get_vectors(n_vectors, mean[k], std[k]):
                q.put(vec)
            vector_queues.append(q)

        t = 0
        # vlc: ['user_id','vector','label','CREATED_AT']
        vlc = []
        X = []
        print("vlc....")
        for row in obs:
            # print("vlc:",t)
            for i in range(len(row)):
                k = int(i/sample_size)
                if t==0:
                    num = row[i]
                else:
                    num = obs[t, i] - obs[t-1, i]
                # print("num",num)
                for j in range(num):
                    vec = vector_queues[k].get()
                    X.append(vec)
                    vlc.append( [i%sample_size, vec, k, t ] )

            t = t+1

        km = KMeans(n_clusters=self.K).fit(X)
        self.centers = km.cluster_centers_

        df = pd.DataFrame(vlc, columns = ['user_id','vector','label','CREATED_AT'])
        return df



    def init_classification(self):
        tweet, user_info = self.read_data_from_xls(self.save_path)

        vlc = self.tweet2vec(tweet)

        self.output(tweet, user_info)
        # print("done")
        return tweet, user_info

if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    print(BASE_DIR)

    save_path = BASE_DIR + '/data/'

    clean_data = Clean_data(save_path, K=3)
    clean_data.init_classification()

    # clean_data.update_classification(save_path + "text_embeddings.txt", {})
