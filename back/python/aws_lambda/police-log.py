import boto3
import os
import uuid
import time
import datetime
import asyncio
import json
import logging
from botocore.client import ClientError

# Initialize Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def set_global_vars():
    """
    Set the Global Variables
    If User provides different values, override defaults
    This function returns the AWS account number
    :return: global_vars
    :rtype: dict
    """
    global_vars = {"status": False}
    try:
        global_vars["Owner"]                    = "20181625"
        global_vars["Environment"]              = ""
        global_vars["aws_region"]               = "ap-northeast-1"
        global_vars["tag_name"]                 = ""
        global_vars["retention_days"]           = 0.1
        global_vars["cw_logs_to_export"]        = ["/aws/lambda/police_protest_info"]
        #global_vars["cw_logs_to_export"]        = os.environ.get("cw_logs_to_export").split(",")
        global_vars["log_dest_bkt"]             = "police-log"
        global_vars["time_out"]                 = 50000
        global_vars["tsk_back_off"]             = 2
        global_vars["status"]                   = True
    except Exception as e:
        logger.error("Unable to set Global Environment variables. Exiting")
        global_vars["error_message"]            = str(e)
    return global_vars

def gen_uuid():
    """ Generates a uuid string and return it """
    return str( uuid.uuid4() )

def gen_ymd_from_epoch(t):
    """ Generates a string of the format "YYYY-MM-DD" from the given epoch time"""
    # Remove the milliseconds
    t = t/1000
    ymd =  ( str(datetime.datetime.utcfromtimestamp(t).year) + \
                "-" + \
                str(datetime.datetime.utcfromtimestamp(t).month) + \
                "-"  + \
                str(datetime.datetime.utcfromtimestamp(t).day) + \
                "-"  + \
                str(datetime.datetime.utcfromtimestamp(t).hour)
    )
    return ymd

def gen_ymd(t,d) -> str:
    """
    Generates a string of the format "YYYY MM DD" from the given datetime, uses the delimited passed
    :param t: Python Datetime
    :param type: Datetime
    :param d: The delimitter to be used
    :param type: str
    :return: ymd Return a "YYYY MM DD" string with the given delimiter
    :rtype: json
    """
    ymd =  ( str(t.year) + d + str(t.month) + d + str(t.day) + d + str(t.hour))
    return ymd

def does_bucket_exists( bucket_name ):
    """
    Check if a given S3 Bucket exists and return a boolean value. The S3 'HEAD' operations are cost effective
    :param name: bucket_name
    :type value: str
    :return: bucket_exists_status
    :rtype: dict
    """
    bucket_exists_status = { 'status':False, 'error_message':'' }
    try:
        s3 = boto3.resource('s3')
        s3.meta.client.head_bucket( Bucket = bucket_name )
        bucket_exists_status['status'] = True
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            bucket_exists_status['status'] = False
            bucket_exists_status['error_message'] = str(e)
        else:
            # logger.error('ERROR: {0}'.format( str(e) ) )
            bucket_exists_status['status'] = False
            bucket_exists_status['error_message'] = str(e)
    return bucket_exists_status

def get_cloudwatch_log_groups(global_vars):
    """
    Get the list of Cloudwatch Log groups
    :param global_vars: The list of global variables
    :param type: json
    :return: resp_data Return a dictionary of data, includes list of 'log_groups'
    :rtype: json
    """
    resp_data = {'status': False, 'log_groups':[], 'error_message': ''}
    client = boto3.client('logs')
    try:
        # Lets get all the logs
        resp = client.describe_log_groups( limit = 50 )
        resp_data['log_groups'].extend( resp.get('logGroups') )
        # Check if the results are paginated
        if resp.get('nextToken'):
            while True:
                resp = client.describe_log_groups( nextToken = resp.get('nextToken'), limit = 50 )
                resp_data['log_groups'].extend( resp.get('logGroups') )
                # Check & Break, if the results are no longer paginated
                if not resp.get('nextToken'):
                    break
        resp_data['status'] = True
    except Exception as e:
        resp_data['error_message'] = str(e)
    return resp_data

def filter_logs_to_export(global_vars, lgs):
    """
    Get a list of log groups to export by applying filter
    :param global_vars: The list of global variables
    :param type: json
    :param lgs: The list of CloudWatch Log Groups
    :param type: json
    :return: resp_data Return a dictionary of data, includes list of filtered 'log_groups'
    :rtype: json
    """
    resp_data = {'status': False, 'log_groups':[], 'error_message': ''}
    # Lets filter for the logs of interest
    for lg in lgs.get('log_groups'):
        if lg.get('logGroupName') in global_vars.get('cw_logs_to_export'):
            resp_data['log_groups'].append(lg)
            resp_data['status'] = True
    return resp_data

async def export_cw_logs_to_s3(global_vars, log_group_name, retention_days, bucket_name, obj_prefix = None):
    """
    Export the logs in the log_group to the given S3 Bucket. Creates a subdirectory(prefix). Defaults to the log group name
    :param global_vars: The list of global variables
    :param type: json
    :param log_group_name: The name of the log group to be exported
    :param type: json
    :param retention_days: The number of days older logs to be archived. Defaults to '90'
    :param type: json
    :param bucket_name: The list of CloudWatch Log Groups
    :param type: str
    :param obj_prefix: The list of CloudWatch Log Groups
    :param type: str
    :return: resp_data Return a dictionary of data, includes list of 'log_groups'
    :rtype: json
    """
    resp_data = {'status': False, 'task_info':{}, 'error_message': ''}
    if not retention_days: retention_days = 90
    if not obj_prefix: obj_prefix = log_group_name.split('/')[-1]
    now_time = datetime.datetime.now()
    # To effectively archive logs
    # Setting for 24 Hour time frame (From:91th day); Captures the 24 hour logs on the 90th day
    n1_day = now_time - datetime.timedelta(days = int(retention_days) + 1)
    # Setting for 24 Hour time frame (Upto:90th day)
    n_day = now_time - datetime.timedelta(days = int(retention_days))
    f_time = int(n1_day.timestamp() * 1000)
    t_time = int(n_day.timestamp() * 1000)
    # To specifially deal with loggroup names without '/'
    if '/' in log_group_name:
        d_prefix = str( log_group_name.replace("/","-")[1:] ) + "/" + str( gen_ymd(n1_day, '/') )
    else:
        d_prefix = str( log_group_name.replace("/","-") ) + "/" + str( gen_ymd(n1_day, '/') )
    # d_prefix = str( log_group_name.replace("/","-")[1:] )
    # Check if S3 Bucket Exists
    resp = does_bucket_exists(bucket_name)
    if not resp.get('status'):
        resp_data['error_message'] = resp.get('error_message')
        return resp_data
    try:
        client = boto3.client('logs')
        r = client.create_export_task(
                taskName = gen_uuid(),
                logGroupName = log_group_name,
                fromTime = f_time,
                to = t_time,
                destination = bucket_name,
                destinationPrefix = d_prefix
                )
        # Get the status of each of those asynchronous export tasks
        r = get_tsk_status(r.get('taskId'), global_vars.get('time_out'), global_vars.get('tsk_back_off'))
        if resp.get('status'):
            resp_data['task_info'] = r.get('tsk_info')
            resp_data['status'] = True
        else:
            resp_data['error_message'] = r.get('error_message')
    except Exception as e:
        resp_data['error_message'] = str(e)
    return resp_data

def get_tsk_status(tsk_id, time_out, tsk_back_off):
    """
    Get the status of the export task list until `time_out`.
    :param tsk_id: The task id of CW Log export
    :param type: str
    :param time_out: The mount of time to wait in seconds
    :param type: str
    :return: resp_data Return a dictionary of data, includes list of 'log_groups'
    :rtype: json
    """
    resp_data = {'status': False, 'tsk_info':{}, 'error_message': ''}
    client = boto3.client('logs')
    if not time_out: time_out = 300
    t = tsk_back_off
    try:
        # Lets get all the logs
        while True:
            time.sleep(t)
            resp = client.describe_export_tasks(taskId = tsk_id)
            tsk_info = resp['exportTasks'][0]
            if t > int(time_out):
                resp_data['error_message'] = f"Task:{tsk_id} is still running. Status:{tsk_info['status']['code']}"
                resp_data['tsk_info'] = tsk_info
                break
            if tsk_info['status']['code'] != "COMPLETED":
                # Crude exponential back off
                t*=2

            else:
                resp_data['tsk_info'] = tsk_info
                resp_data['status'] = True
                break
    except Exception as e:
        resp_data['error_message'] = f"Unable to verify status of task:{tsk_id}. ERROR:{str(e)}"
    resp_data['tsk_info']['time_taken'] = t
    logger.info(f"It took {t} seconds to explort Log Group:'{tsk_info.get('logGroupName')}'")
    return resp_data

def lambda_handler(event, context):
    """
    Entry point for all processing. Load the global_vars
    :return: A dictionary of tagging status
    :rtype: json
    """
    """
    Can Override the global variables using Lambda Environment Parameters
    """
    global_vars = set_global_vars()

    resp_data = {"status": False, "error_message" : '' }

    if not global_vars.get('status'):
        logger.error('ERROR: {0}'.format( global_vars.get('error_message') ) )
        resp_data['error_message'] = global_vars.get('error_message')
        return resp_data

    lgs = get_cloudwatch_log_groups(global_vars)
    if not lgs.get('status'):
        logger.error(f"Unable to get list of cloudwatch Logs.")
        resp_data['error_message'] = lgs.get('error_message')
        return resp_data

    f_lgs = filter_logs_to_export(global_vars, lgs)
    if not (f_lgs.get('status') or f_lgs.get('log_groups')):
        err = f"There are no log group matching the filter or Unable to get a filtered list of cloudwatch Logs."
        logger.error( err )
        resp_data['error_message'] = f"{err} ERROR:{f_lgs.get('error_message')}"
        resp_data['lgs'] = {'all_logs':lgs, 'cw_logs_to_export':global_vars.get('cw_logs_to_export'), 'filtered_logs':f_lgs}
        return resp_data

    # TODO: This can be a step function (or) async 'ed
    resp_data['export_tasks'] = []
    #loop = asyncio.get_event_loop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # asyncio.set_event_loop(asyncio.new_event_loop())
    # wait_coro = asyncio.wait(to_do) 
    # res, _ = loop.run_until_complete(wait_coro)

    # Lets being the archving/export process
    for lg in f_lgs.get('log_groups'):
        resp = loop.run_until_complete( export_cw_logs_to_s3( global_vars, lg.get('logGroupName'),global_vars.get('retention_days'), global_vars.get('log_dest_bkt')) )
        print(resp)
        resp_data['export_tasks'].append(resp)
    loop.close()
    # If the execution made it through here, no errors in triggering the export tasks. Set to True.
    resp_data['status'] = True
    return resp_data

if __name__ == '__main__':
    lambda_handler(None, None)
