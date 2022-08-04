'''
 An UDF implementation of predicting room occupancy, based upon models generated using AutoGLuon (AutoML) library.
'''

from _snowflake import vectorized
import _snowflake
import os ,sys ,json ,zipfile ,tarfile
import importlib.util
import pandas as pd
import requests # needed by autogluon, though i realize this wont work
import logging
import numpy as np

# The snowflake directory, which would contain the various artifacts that we
# had defined as imports
IMPORT_DIR = sys._xoptions["snowflake_import_directory"]

# This is a local directoy, used for storing the various artifacts locally
LOCAL_TEMP_DIR = f'/tmp/autog_'
TARGET_MODEL_DIR_PATH = os.path.join(LOCAL_TEMP_DIR, 'ml_model')
TARGET_LIB_PATH = os.path.join(LOCAL_TEMP_DIR, 'lib')

# We perform extraction only on a first run. Hence this simplistic check
# can help in doing this extraction multiple times.
if os.path.exists(LOCAL_TEMP_DIR) == False:
    # --- Model extraction ------
    # We un-archive the models into a seperate local directory
    MODEL_ARCHIVE_FL = 'room_occupancy_autogluon_model.tar.gz' # <== TODO: THIS SHOULD BE DYNAMIC AND NOT HARD CODED

    # Extract the library
    tf = tarfile.open(f'{IMPORT_DIR}{MODEL_ARCHIVE_FL}')
    tf.extractall(f'{TARGET_MODEL_DIR_PATH}')

    # --- Library extraction ------
    # We extract each of the autogluon library locally into its own directory

    wheel_files = [
        'autogluon.core-0.5.2-py3-none-any.whl'
        ,'autogluon.common-0.5.2-py3-none-any.whl'
        ,'autogluon.extra-0.3.1-py3-none-any.whl'
        ,'autogluon.features-0.5.2-py3-none-any.whl'
        ,'autogluon.tabular-0.5.2-py3-none-any.whl'
        ,'autogluon-0.5.2-py3-none-any.whl'
    ] # <== TODO: THIS SHOULD BE DYNAMIC AND NOT HARD CODED
    for wheel_fl in wheel_files:
        with zipfile.ZipFile( os.path.join(IMPORT_DIR, wheel_fl) , 'r') as zip_ref:
            zip_ref.extractall(TARGET_LIB_PATH)

# We need to add the libraries to the system path, so that
# the various autogluon modules can be imported
sys.path.insert(0 ,os.path.join(TARGET_LIB_PATH, 'autogluon/tabular/models') )
sys.path.insert(0 ,TARGET_LIB_PATH )
 
#Import should be done, only after inserting the target_lib_path into the path
from autogluon.tabular import TabularDataset, TabularPredictor

#Load the model and initialize the predictor
predictor = TabularPredictor.load(f'{TARGET_MODEL_DIR_PATH}/model' ,require_version_match=False) 

# The predict function, which will be invoked as part of the UDF. The
# set of columns would be passed into the function as dataframe. Also the
# model that need to be used for predicts, would be passed in via the 
# dataframe
@vectorized(input=pd.DataFrame)
def predict_occupancy(p_df):

    # Snowpark currently does not set the column name in the input dataframe
    # The default col names are like 0,1,2,... Hence we need to reset the column
    # names to the features that we initially used for training. 
    p_df.columns = ['MODEL_TOUSE' ,'CO2' ,'HUMIDITY' ,'LIGHT' ,'TEMPERATURE' ,'PIR']
    
    # The AutoGluon model to use for predicting
    model_touse = p_df['MODEL_TOUSE'][0]

    # Project to only those columns that were used during training
    source_df = p_df[['CO2' ,'HUMIDITY' ,'LIGHT' ,'TEMPERATURE' ,'PIR']]

    # Perform prediction
    y_pred = predictor.predict(source_df, model=model_touse)

    return y_pred

# predict_occupancy._sf_vectorized_input = pd.DataFrame
# predict_occupancy._sf_max_batch_size = 10
