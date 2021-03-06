from MLFE import load
from MLFE import Model
from MLFE import Buffer
from MLFE import Env
from MLFE import updateTargetGraph
from MLFE import updateTarget
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression,Lasso
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import StratifiedKFold,KFold
from cleanlab.pruning import get_noise_indices
from sklearn.metrics import matthews_corrcoef
from utils import *
from args import args
import tensorflow as tf
import os
import numpy as np
from sklearn import metrics
import tqdm
import copy
import warnings
import math

warnings.filterwarnings('ignore')
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

tf_config = tf.ConfigProto()
tf_config.gpu_options.per_process_gpu_memory_fraction = 0.1

def main(ii, string, classifier):
    opt_type= 'o1'
    opt_size = 9 if opt_type =='o1' else 5
    buffer_size = 2000
    seed = 3
    num_epochs = 50000
    n_jobs = 1
    tau = 0.05
    gamma = 0.9
    epsilon = 1
    batch_size = 100
    save_model = True
    train = True
    test = True
    out_dir = './out/'+string+'/safem'+str(ii)
    model_dir = './out/'+string+'/safem_model'+str(ii)
    if not os.path.isdir('./out/'+string):
        os.mkdir('./out/'+string)
    if not os.path.isdir(model_dir):
        os.mkdir(model_dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    did = 1480
    f_dataset = "./dataset/"+string+"-train"+str(ii)+".arff"
    dataset, tasktype = load(f_path=f_dataset)
    f_dataset1 = "./dataset/"+string+"-test"+str(ii)+".arff"
    dataset_test, tasktype = load(f_path=f_dataset1)
    input_size = 20*(dataset.shape[1]-1)

    globalbuff = Buffer(buffer_size)
    if train:
        for g in tqdm.tqdm(range(num_epochs), total=num_epochs):
            modelNetwork = Model(opt_size=opt_size, input_size=input_size, name="model", maml=False)
            targetNetwork = Model(opt_size=opt_size, input_size=input_size, name="target", maml=False)

            perf = 0
            pretransform = []
            with tf.Session(config=tf_config) as sess:
                saver = tf.train.Saver()
                if g == 0:
                    sess.run(modelNetwork.init_op)
                    sess.run(targetNetwork.init_op)

                    env = Env(dataset, feature=0, opt_type=opt_type, random_state=seed,
                              tasktype=tasktype, pretransform=None, n_jobs=n_jobs,
                              evaluatertype=classifier)
                    print("training init perform", env.init_pfm)
                    f = open(os.path.join(out_dir, "succeed.csv"), 'a')
                    f.write("%d,%.6f\n" % (g - 1, env.init_pfm))
                    f.close()

                    rf1 = GaussianNB()
                    rf1.fit(dataset[:, 0:-1], dataset[:, -1])
                    pre = rf1.predict(dataset_test[:, 0:-1])
                    init_pfm1 = metrics.f1_score(dataset_test[:, -1], pre, pos_label=1, average="binary")
                    print("testing init perform", init_pfm1)
                    f = open(os.path.join(out_dir, "test_succeed.csv"), 'a')
                    f.write("%d,%.6f\n" % (g - 1, init_pfm1))
                    f.close()

                    mcc=matthews_corrcoef(dataset_test[:, -1], pre)
                    f = open(os.path.join(out_dir, "test_mcc.csv"), 'a')
                    f.write("%d,%.6f\n" % (g - 1, mcc))
                    f.close()

                    prob = rf1.predict_proba(dataset_test[:, 0:-1])
                    thresholds = metrics.roc_auc_score(dataset_test[:, -1], prob[:, -1])
                    f = open(os.path.join(out_dir, "test_auc.csv"), 'a')
                    f.write("%d,%.6f\n" % (g - 1, thresholds))
                    f.close()
                else:
                    saver.restore(sess, model_dir+ "/model.ckpt")

                trainables = tf.trainable_variables()
                updateOps = updateTargetGraph(trainables, tau)  # ??????target??????????????????


                for fid in tqdm.tqdm(range(dataset.shape[1] - 1), total=dataset.shape[1] - 1):

                    env = Env(dataset, feature=fid, opt_type=opt_type,random_state=seed,
                              tasktype=tasktype, pretransform=pretransform, n_jobs=n_jobs,
                              evaluatertype=classifier)

                    tmp_buffer = []
                    s = np.copy(env.state)
                    act_mask = np.copy(env.action_mask)

                    Q = sess.run(modelNetwork.Q_, feed_dict={modelNetwork.inputs: [s]})[0]
                    action = np.ma.masked_array(Q, mask=act_mask).argmax()
                    # print('Q????????????',action)

                    if np.random.rand(1) < epsilon:
                        action = np.ma.masked_array(np.random.rand(opt_size), mask=act_mask).argmax()
                        # print('???????????????', action)

                    s_next, reward = env.step(action)
                    perf += reward

                    tmp_buffer.append(np.copy([s, action, reward, s_next, act_mask]))
                    pretransform.append((fid, '_'.join(env.best_seq)))
                    for val in tmp_buffer:
                        globalbuff.add(val)

                    # print(total_reward)
                f = open(os.path.join(out_dir, "reward.csv"), 'a')
                f.write("%d,%.6f\n" % (g , perf))
                f.close()
                if g>50:
                    experience = globalbuff.sample(batch_size)
                    # print(experience.shape)
                    s, a, r, s_next, act_mask = [np.squeeze(elem, axis=1) for elem in
                                                 np.split(experience, 5, 1)]
                    s = np.array([ss for ss in s])
                    s = np.reshape(s, (batch_size, input_size))
                    # print(s_next.shape)
                    s_next = np.array([ss for ss in s_next])
                    # print(s_next.shape)
                    s_next = np.reshape(s_next, (batch_size, input_size))
                    act_mask = np.array([am for am in act_mask])
                    act_mask = np.reshape(act_mask, (batch_size, opt_size))

                    Q1 = sess.run(modelNetwork.Q_, feed_dict={modelNetwork.inputs: s_next})
                    Q2 = sess.run(targetNetwork.Q_, feed_dict={targetNetwork.inputs: s_next})
                    # doubleQ = Q2[:, np.argmax(ma.masked_array(Q1, mask=act_mask), axis=-1)]
                    doubleQ = np.array([Q2[i][ss] for i, ss in
                                        enumerate(np.argmax(np.ma.masked_array(Q1, mask=act_mask), axis=-1))])

                    Q_target = r + gamma * doubleQ
                    _, loss = sess.run([modelNetwork.train_op, modelNetwork.loss],
                                       feed_dict={modelNetwork.inputs: s, modelNetwork.Q_next: Q_target,
                                                  modelNetwork.action: a})
                    # print(loss)

                    f = open(os.path.join(out_dir, "loss.csv"), 'a')
                    f.write("%.6f\n" % (loss))
                    f.close()

                    print('loss is ' + str(ii) + ':' + str(g) + ':' + str(fid) + ':' + str(loss))

                    updateTarget(updateOps, sess)

                saver = tf.train.Saver()
                saver.save(sess, model_dir+ "/model.ckpt")


                f = open(os.path.join(out_dir, "succeed1.csv"), 'a')
                env_train1 = Env(dataset, feature=0, opt_type=opt_type,random_state=seed,
                                 tasktype=tasktype, pretransform=pretransform, n_jobs=n_jobs,
                                 evaluatertype=classifier)

                f.write("%d,%.6f\n" % (g, env_train1.init_pfm))
                f.close()

                print(str(ii) + ':' + str(g) + 'training is done!')
                for act in pretransform:
                    print(act)

                testdecay = 1
                if (g + 1) % 10 == 0:

                    pretransform_test = []

                    for fid in tqdm.tqdm(range(dataset.shape[1] - 1), total=dataset.shape[1] - 1):
                        env_test = Env(dataset, feature=fid,  opt_type=opt_type,tasktype=tasktype,
                                       random_state=seed, pretransform=pretransform_test, n_jobs=n_jobs,
                                       evaluatertype=classifier)

                        s = np.copy(env_test.state)
                        act_mask = np.copy(env_test.action_mask)
                        Q = sess.run(modelNetwork.Q_, feed_dict={modelNetwork.inputs: [s]})
                        action = np.ma.masked_array(Q, mask=act_mask).argmax()
                        s_next, reward = env_test.step(action)

                        pretransform_test.append((fid, '_'.join(env_test.best_seq)))

                    f = open(os.path.join(out_dir, "test_succeed_feat.csv"), 'a')
                    for val in pretransform_test:
                        f.write("%d,%s\n" % (val[0], val[1]))
                    f.close()
                    f = open(os.path.join(out_dir, "succeed.csv"), 'a')
                    env_test1 = Env(dataset, feature=fid,opt_type=opt_type,tasktype=tasktype,
                                   random_state=seed, pretransform=pretransform_test, n_jobs=n_jobs,
                                   evaluatertype=classifier)

                    f.write("%d,%.6f\n" % (g, env_test1.init_pfm))
                    f.close()

                    dataset1 = np.vstack((dataset, dataset_test))
                    env1 = Env(dataset1, feature=0, opt_type=opt_type,tasktype=tasktype,
                               random_state=seed, pretransform=pretransform_test, n_jobs=n_jobs,
                               evaluatertype=classifier)
                    dataset1_ = copy.deepcopy(env1.origin_dataset)
                    print('dataset1_:', env1.origin_dataset.shape[1] - 1)
                    kk = dataset.shape[0]
                    X_train1, X_test1 = dataset1_[0:kk, 0:-1], dataset1_[kk:, 0:-1]
                    y_train1, y_test1 = dataset1_[0:kk, -1], dataset1_[kk:, -1]
                    rf1 = GaussianNB()
                    rf1.fit(X_train1, y_train1)
                    pre = rf1.predict(X_test1)
                    final_pfm = metrics.f1_score(y_test1, pre, pos_label=1, average="binary")
                    f = open(os.path.join(out_dir, "test_succeed.csv"), 'a')
                    f.write("%d,%.6f\n" % (g, final_pfm))
                    f.close()

                    mcc = matthews_corrcoef(y_test1, pre)
                    f = open(os.path.join(out_dir, "test_mcc.csv"), 'a')
                    f.write("%d,%.6f\n" % (g, mcc))
                    f.close()

                    prob = rf1.predict_proba(X_test1)
                    thresholds = metrics.roc_auc_score(y_test1, prob[:, -1])
                    f = open(os.path.join(out_dir, "test_auc.csv"), 'a')
                    f.write("%d,%.6f\n" % (g, thresholds))
                    f.close()

                    for act in pretransform_test:
                        print(act)

                if g<=100:
                    epsilon=epsilon*0.99
                else:
                    epsilon=0.0001
                print(str(ii) + ':' + str(g) + ' step is done!')
                print('epsilon:', epsilon)
            tf.reset_default_graph()

if __name__ == "__main__":
    classifier = 'nb'  # lr, rf
    project = 'synapse-1-1'  # the name of the project
    for i in range(5):
        main(i, project, classifier)