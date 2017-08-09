# -*- coding: utf-8 -*-
############################################################
#
# Autogenerated by the KBase type compiler -
# any changes made here will be overwritten
#
############################################################

from __future__ import print_function
# the following is a hack to get the baseclient to import whether we're in a
# package or not. This makes pep8 unhappy hence the annotations.
try:
    # baseclient and this client are in a package
    from .baseclient import BaseClient as _BaseClient  # @UnusedImport
except:
    # no they aren't
    from baseclient import BaseClient as _BaseClient  # @Reimport
import time


class kb_cufflinks(object):

    def __init__(
            self, url=None, timeout=30 * 60, user_id=None,
            password=None, token=None, ignore_authrc=False,
            trust_all_ssl_certificates=False,
            auth_svc='https://kbase.us/services/authorization/Sessions/Login',
            service_ver=None,
            async_job_check_time_ms=100, async_job_check_time_scale_percent=150, 
            async_job_check_max_time_ms=300000):
        if url is None:
            raise ValueError('A url is required')
        self._service_ver = service_ver
        self._client = _BaseClient(
            url, timeout=timeout, user_id=user_id, password=password,
            token=token, ignore_authrc=ignore_authrc,
            trust_all_ssl_certificates=trust_all_ssl_certificates,
            auth_svc=auth_svc,
            async_job_check_time_ms=async_job_check_time_ms,
            async_job_check_time_scale_percent=async_job_check_time_scale_percent,
            async_job_check_max_time_ms=async_job_check_max_time_ms)

    def _check_job(self, job_id):
        return self._client._check_job('kb_cufflinks', job_id)

    def _run_cufflinks_submit(self, params, context=None):
        return self._client._submit_job(
             'kb_cufflinks.run_cufflinks', [params],
             self._service_ver, context)

    def run_cufflinks(self, params, context=None):
        """
        :param params: instance of type "CufflinksParams" -> structure:
           parameter "workspace_name" of String, parameter
           "alignment_object_ref" of String, parameter
           "expression_set_suffix" of String, parameter "expression_suffix"
           of String, parameter "genome_ref" of String, parameter
           "num_threads" of Long, parameter "min_intron_length" of Long,
           parameter "max_intron_length" of Long, parameter
           "overhang_tolerance" of Long
        :returns: instance of type "CufflinksResult" (result_directory:
           folder path that holds all files generated by the cufflinks run
           expression_obj_ref: generated Expression/ExpressionSet object
           reference exprMatrix_FPKM/TPM_ref: generated FPKM/TPM
           ExpressionMatrix object reference report_name: report name
           generated by KBaseReport report_ref: report reference generated by
           KBaseReport) -> structure: parameter "result_directory" of String,
           parameter "expression_obj_ref" of type "obj_ref" (An X/Y/Z style
           reference), parameter "exprMatrix_FPKM_ref" of type "obj_ref" (An
           X/Y/Z style reference), parameter "exprMatrix_TPM_ref" of type
           "obj_ref" (An X/Y/Z style reference), parameter "report_name" of
           String, parameter "report_ref" of String
        """
        job_id = self._run_cufflinks_submit(params, context)
        async_job_check_time = self._client.async_job_check_time
        while True:
            time.sleep(async_job_check_time)
            async_job_check_time = (async_job_check_time *
                self._client.async_job_check_time_scale_percent / 100.0)
            if async_job_check_time > self._client.async_job_check_max_time:
                async_job_check_time = self._client.async_job_check_max_time
            job_state = self._check_job(job_id)
            if job_state['finished']:
                return job_state['result'][0]

    def run_Cuffdiff(self, params, context=None):
        """
        :param params: instance of type "CuffdiffInput" (Required input
           parameters for run_Cuffdiff. expressionset_ref           -  
           reference for an expressionset object workspace_name             
           -   workspace name to save the differential expression output
           object output_obj_name             -   name of the differential
           expression matrix set output object) -> structure: parameter
           "expressionset_ref" of type "obj_ref" (An X/Y/Z style reference),
           parameter "workspace_name" of String, parameter "output_obj_name"
           of String, parameter "library_norm_method" of String, parameter
           "multi_read_correct" of type "boolean" (A boolean - 0 for false, 1
           for true. @range (0, 1)), parameter "time_series" of type
           "boolean" (A boolean - 0 for false, 1 for true. @range (0, 1)),
           parameter "min_alignment_count" of Long
        :returns: instance of type "CuffdiffResult" -> structure: parameter
           "result_directory" of String, parameter "diffExprMatrixSet_ref" of
           type "obj_ref" (An X/Y/Z style reference), parameter "report_name"
           of String, parameter "report_ref" of String
        """
        return self._client.call_method(
            'kb_cufflinks.run_Cuffdiff',
            [params], self._service_ver, context)

    def status(self, context=None):
        return self._client.call_method('kb_cufflinks.status',
                                        [], self._service_ver, context)
