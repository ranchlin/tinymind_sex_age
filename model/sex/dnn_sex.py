from keras import models
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.layers import BatchNormalization
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.core import Dense, Activation, Dropout
from keras.models import Sequential
from keras.optimizers import Adam
from sklearn.cross_validation import train_test_split

from tiny.tfidf import *
from tiny.usage import *

from sklearn.metrics import log_loss
tmp_model = './model/checkpoint/dnn_best_tmp.hdf5'
np.random.seed(47)

version = '1002'

def train_dnn(dropout, lr):
    #dropout = 0.7

    args = locals()
    logger.debug(f'Run train dnn:{args}')


    feature_label = get_feature_label_dnn(version)


    test = feature_label[feature_label['sex'].isnull()]
    train=feature_label[feature_label['sex'].notnull()]


    X_train, X_test, y_train, y_test = split_train(train, label_col = 'sex')



    print(X_train.shape, y_train.shape)
    input_dim = X_train.shape[1]

    model = Sequential()
    model.add(Dense(1200, input_shape=(input_dim,)))
    #model.add(Activation('sigmoid'))
    model.add(LeakyReLU(alpha=0.01))
    model.add(Dropout(dropout))


    model.add(Dense(100))
    model.add(LeakyReLU(alpha=0.01))
    model.add(BatchNormalization())
    model.add(Dropout(dropout))


    model.add(Dense(15, ))
    model.add(LeakyReLU(alpha=0.01))


    model.add(Dense(2, ))
    model.add(Activation('sigmoid'))

    # model.compile(optimizer="sgd", loss="mse")
    adam = Adam(lr=lr)
    model.compile(loss='binary_crossentropy', optimizer=adam,
                    #metrics=['categorical_crossentropy'],
                  )
    print(model.summary())
    #model.compile(loss='binary_crossentropy', optimizer='adam', metrics=[categorical_accuracy])

    #'./model/'
    file_path = tmp_model

    check_best = ModelCheckpoint(filepath=replace_invalid_filename_char(file_path),
                                monitor='val_loss',verbose=1,
                                save_best_only=True, mode='min')

    early_stop = EarlyStopping(monitor='val_loss',verbose=1,
                               patience=300,
                               )
    from keras.utils import np_utils
    print(y_train.shape)
    history = model.fit(X_train, np_utils.to_categorical(y_train),
                        validation_data=(X_test, np_utils.to_categorical(y_test)),
                        callbacks=[check_best, early_stop],
                        batch_size=128,
                        #steps_per_epoch= len(X_test)//128,
                        epochs=2000,
                        verbose=1,
                        )

    best = log_loss(y_test, model.predict_proba(X_test))

    logger.debug(f'Real time best:{best}')

    return model, history, args


def get_feature_label_dnn(version):
    from tiny.util import get_stable_feature
    feature_label = get_stable_feature(version)
    feature_label['sex'] = feature_label['sex'].astype('category')
    feature_label['sex_age'] = feature_label['sex_age'].astype('category')
    return feature_label


if __name__ == '__main__':
    for drop in [0.75,0.8, 0.7,] :
        for lr in [0.0005, 0.0003, 0.0001]:
            _ , history, args = train_dnn(drop, lr)

            best_epoch = np.array(history.history['val_loss']).argmin()+1
            best_score = np.array(history.history['val_loss']).min()

            model = models.load_model(tmp_model)

            feature_label = get_feature_label_dnn(version)

            test = feature_label[feature_label['sex'].isnull()]
            train = feature_label[feature_label['sex'].notnull()]

            X_train, X_test, y_train, y_test = split_train(train, label_col = 'sex')

            classifier = model

            pre_x = test.drop(['sex', 'age', 'sex_age', 'device'], axis=1)
            sub = pd.DataFrame(classifier.predict_proba(pre_x.values))

            sub.columns = train.sex.cat.categories
            sub['DeviceID'] = test['device'].values


            best = log_loss(y_test, classifier.predict_proba(X_test))

            logger.debug(f'Best:{best}, best_score:{best_score} @ epoch:{best_epoch}')


            model_file = f'./model/checkpoint/dnn_best_{best}_{args}_epoch_{best_epoch}.hdf5'
            model.save(model_file,
                       overwrite=True)

            print(
                f'=============Final train feature({len(feature_label.columns)}):\n{list(feature_label.columns)} \n {len(feature_label.columns)}')

            file = f'./sub/baseline_dnn_{best}_{args}_epoch_{best_epoch}.csv'
            from tiny.util import replace_invalid_filename_char, save_result_for_ensemble

            file = replace_invalid_filename_char(file)
            logger.info(f'sub file save to {file}')
            sub = round(sub, 10)
            sub.to_csv(file, index=False)

            ###Save result for ensemble
            train_bk = pd.DataFrame(classifier.predict_proba( train.drop(['sex', 'age', 'sex_age', 'device'], axis=1) ),
                                 index = train.device,
                                 columns= train.sex.cat.categories
                                 )

            test_bk = pd.DataFrame(classifier.predict_proba(pre_x.values),
                                 index = test.device,
                                 columns= test.sex.cat.categories
                                 )
            # label_bk = pd.DataFrame({'label':train.sex_age.cat.codes},
            #                      index = train.device,
            #                      )

            save_result_for_ensemble(f'{best_score}_{best_epoch}_v_{version}_dnn_sex_{args}',
                                         train = train_bk,
                                         test  = test_bk ,
                                         label = None,
                                     )