import time
import jionlp

def extract_time(text: str, to_time_point: bool = True):
    """core.util.extract_time()的修改版, 添加时间基参数time.time()"""
    
    result = jionlp.ner.extract_time(text, time_base=time.time()) # <- 添加时间基参数time.time()
    if result:
        try:
            detail = result[0]['detail']

            if detail['type'] in ['time_span', 'time_point']:
                return [time.strptime(n, '%Y-%m-%d %H:%M:%S') for n in detail['time'] if n != 'inf']

            elif detail['type'] == 'time_delta':
                time_length = {
                    'year': 31536000,
                    'month': 2628000,
                    'day': 86400,
                    'hour': 3600,
                    'minute': 60,
                    'second': 1
                }
                time_result = 0
                for k, v in time_length.items():
                    if k in detail['time']:
                        if to_time_point:
                            return [time.localtime(time.time() + detail['time'][k] * v)]
                        time_result += detail['time'][k] * v
                return time_result

            elif detail['type'] == 'time_period':
                pass

        except OSError:
            pass
    return []
