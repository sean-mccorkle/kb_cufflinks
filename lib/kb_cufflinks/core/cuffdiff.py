import os
import uuid
from pprint import pprint
import zipfile
import re
import glob
import multiprocessing as mp
import handler_utils
import script_utils
from cuffmerge import CuffMerge
from cuffdiff_output import process_cuffdiff_file

from Workspace.WorkspaceClient import Workspace as Workspace
from DataFileUtil.DataFileUtilClient import DataFileUtil
from DataFileUtil.baseclient import ServerError as DFUError
from GenomeFileUtil.GenomeFileUtilClient import GenomeFileUtil
from ReadsAlignmentUtils.ReadsAlignmentUtilsClient import ReadsAlignmentUtils
from ExpressionUtils.ExpressionUtilsClient import ExpressionUtils
from DifferentialExpressionUtils.DifferentialExpressionUtilsClient import DifferentialExpressionUtils
from KBaseReport.KBaseReportClient import KBaseReport

class CuffDiff:

    PARAM_IN_WS_NAME = 'workspace_name'
    PARAM_IN_OBJ_NAME = 'output_obj_name'
    PARAM_IN_EXPSET_REF = 'expressionset_ref'

    GFFREAD_TOOLKIT_PATH = '/kb/deployment/bin/gffread'

    def _process_params(self, params):
        """
        validates params passed to run_CuffDiff method
        """
        for p in [self.PARAM_IN_EXPSET_REF,
                  self.PARAM_IN_OBJ_NAME,
                  self.PARAM_IN_WS_NAME
                 ]:
            if p not in params:
                raise ValueError('"{}" parameter is required, but missing'.format(p))

        ws_name_id = params.get(self.PARAM_IN_WS_NAME)
        if not isinstance(ws_name_id, int):
            try:
                ws_name_id = self.dfu.ws_name_to_id(ws_name_id)
            except DFUError as se:
                prefix = se.message.split('.')[0]
                raise ValueError(prefix)

    def _get_genome_gtf_file(self, gnm_ref, gtf_file_dir):
        """
        Get data from genome object ref and return the GTF filename (with path)
        """
        self.logger.info("Converting genome {0} to GTF file {1}".format(gnm_ref, gtf_file_dir))
        try:
            gfu_ret = self.gfu.genome_to_gff({'genome_ref': gnm_ref,
                                         'is_gtf': 1,
                                         'target_dir': gtf_file_dir})
        except ValueError as egfu:
            self.logger.info('GFU getting GTF file raised error:\n')
            pprint(egfu)
            return None
        else:  # no exception raised
            return gfu_ret.get('file_path')

    def _generate_output_file_list(self, result_directory):
        """
        _generate_output_file_list: zip result files and generate file_links for report
        """
        self.logger.info('Start packing result files')
        output_files = list()

        output_directory = os.path.join(self.scratch, 'outfile_' + str(uuid.uuid4()))
        handler_utils._mkdir_p(output_directory)
        result_file = os.path.join(output_directory, 'cuffdiff_result.zip')
        plot_file = os.path.join(output_directory, 'cuffdiff_plot.zip')

        with zipfile.ZipFile(result_file, 'w',
                             zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zip_file:
            for root, dirs, files in os.walk(result_directory):
                for file in files:
                    if not (file.endswith('.zip') or
                                file.endswith('.png') or
                                file.endswith('.DS_Store')):
                        zip_file.write(os.path.join(root, file), file)

        output_files.append({'path': result_file,
                             'name': os.path.basename(result_file),
                             'label': os.path.basename(result_file),
                             'description': 'File(s) generated by Cuffdiff App'})

        return output_files

    def _generate_html_report(self, result_directory,
                                       diff_expression_obj_ref,
                                       genome_ref):
        """
        _generate_html_report: generate html summary report
        """

        self.logger.info('start generating html report')
        html_report = list()

        output_directory = os.path.join(self.scratch, str(uuid.uuid4()))
        handler_utils._mkdir_p(output_directory)
        result_file_path = os.path.join(output_directory, 'report.html')

        diff_expr_set = self.ws_client.get_objects2({'objects':
                                                       [{'ref':
                                                             diff_expression_obj_ref}]})['data'][0]
        diff_expr_set_data = diff_expr_set['data']
        diff_expr_set_info = diff_expr_set['info']
        diff_expr_set_name = diff_expr_set_info[1]

        overview_content = ''
        overview_content += '<br/><table><tr><th>Generated DifferentialExpressionMatrixSet'
        overview_content += ' Object</th></tr>'
        overview_content += '<tr><td>{} ({})'.format(diff_expr_set_name,
                                                     diff_expression_obj_ref)
        overview_content += '</td></tr></table>'

        overview_content += '<p><br/></p>'

        overview_content += '<br/><table><tr><th>Generated DifferentialExpressionMatrix'
        overview_content += ' Object</th><th></th><th></th><th></th></tr>'
        overview_content += '<tr><th>Differential Expression Matrix Name</th>'
        overview_content += '<th>Condition 1</th>'
        overview_content += '<th>Condition 2</th>'
        overview_content += '</tr>'

        for item in diff_expr_set_data['items']:
            item_diffexprmatrix_object = self.ws_client.get_objects2({'objects':
                                                               [{'ref': item['ref']}]})['data'][0]
            item_diffexprmatrix_info = item_diffexprmatrix_object['info']
            item_diffexprmatrix_data = item_diffexprmatrix_object['data']
            diffexprmatrix_name = item_diffexprmatrix_info[1]

            overview_content += '<tr><td>{} ({})</td>'.format(diffexprmatrix_name,
                                                              item['ref'])
            overview_content += '<td>{}</td>'.format(item_diffexprmatrix_data.
                                                     get('condition_mapping').keys()[0])
            overview_content += '<td>{}</td>'.format(item_diffexprmatrix_data.
                                                     get('condition_mapping').values()[0])
            overview_content += '</tr>'
        overview_content += '</table>'

        with open(result_file_path, 'w') as result_file:
            with open(os.path.join(os.path.dirname(__file__), 'report_template.html'),
                      'r') as report_template_file:
                report_template = report_template_file.read()
                report_template = report_template.replace('<p>Overview_Content</p>',
                                                          overview_content)
                result_file.write(report_template)

        report_shock_id = self.dfu.file_to_shock({'file_path': output_directory,
                                                  'pack': 'zip'})['shock_id']

        html_report.append({'shock_id': report_shock_id,
                            'name': os.path.basename(result_file_path),
                            'label': os.path.basename(result_file_path),
                            'description': 'HTML summary report for Cuffdiff App'})
        return html_report

    def _generate_report(self, diff_expression_obj_ref, genome_ref,
                         params, result_directory):
        """
        _generate_report: generate summary report
        """
        self.logger.info('Creating report')

        output_files = self._generate_output_file_list(result_directory)

        output_html_files = self._generate_html_report(result_directory,
                                                        diff_expression_obj_ref,
                                                        genome_ref)
        diff_expr_set_data = self.ws_client.get_objects2({'objects':
                                                        [{'ref':
                                                        diff_expression_obj_ref}]})['data'][0]['data']

        objects_created = [{'ref': diff_expression_obj_ref,
                            'description': 'Differential Expression Matrix Set generated by Cuffdiff'}]

        items = diff_expr_set_data['items']
        for item in items:
            objects_created.append({'ref': item['ref'],
                                    'description': 'Differential Expression Matrix generated by Cuffdiff'})
        report_params = {
                         'message': '',
                         'workspace_name': params.get('workspace_name'),
                         'file_links': output_files,
                         'objects_created': objects_created,
                         'html_links': output_html_files,
                         'direct_html_link_index': 0,
                         'html_window_height': 333,
                         'report_object_name': 'kb_cuffdiff_report_' + str(uuid.uuid4())
                         }

        kbase_report_client = KBaseReport(self.callback_url)
        output = kbase_report_client.create_extended_report(report_params)

        report_output = {'report_name': output['name'], 'report_ref': output['ref']}

        return report_output

    def _get_rnaseq_expressionset_data(self, expression_set_data, result_directory):
        """
        Get data from expressionset object in the form required 
        for input to cuffmerge and cuffdiff
        """
        self.logger.info('Getting data from RNASeq expression set input')

        output_data = {}
        output_data['alignmentSet_id'] = expression_set_data.get('alignmentSet_id')
        output_data['sampleset_id'] = expression_set_data.get('sampleset_id')
        output_data['genome_id'] = expression_set_data.get('genome_id')
        """
        Get gtf file from genome_ref. Used as input to cuffmerge.
        """
        output_data['gtf_file_path'] = self._get_genome_gtf_file(output_data['genome_id'],
                                                                 self.scratch)
        condition = []
        bam_files = []

        mapped_expr_ids = expression_set_data.get('mapped_expression_ids')

        assembly_file = os.path.join(result_directory, "assembly_gtf.txt")
        list_file = open(assembly_file, 'w')
        for i in mapped_expr_ids:
            for alignment_id, expression_id in i.items():
                """
                assembly_gtf.txt will contain the file paths of all .gtf files 
                in the expressionset. Used as input to cuffmerge.
                """
                expression_retVal = self.eu.download_expression({'source_ref': expression_id})
                expression_dir = expression_retVal.get('destination_dir')
                e_file_path = os.path.join(expression_dir, "transcripts.gtf")

                if os.path.exists(e_file_path):
                    self.logger.info('Adding:  ' + expression_id + ':, ' + e_file_path)
                    list_file.write("{0}\n".format(e_file_path))
                else:
                    raise ValueError(e_file_path + " not found")
                """
                Create a list of all conditions in expressionset. Used as input to cuffdiff.
                """
                alignment_data = self.ws_client.get_objects2(
                    {'objects':
                         [{'ref': alignment_id}]})['data'][0]['data']
                alignment_condition = alignment_data.get('condition')
                if alignment_condition not in condition:
                    condition.append(alignment_condition)
                """
                Create a list of bam files in alignment set. Used as input to cuffdiff.
                """
                alignment_retVal = self.rau.download_alignment({'source_ref': alignment_id})
                alignment_dir = alignment_retVal.get('destination_dir')
                align_path, align_dir = os.path.split(alignment_dir)
                new_alignment_dir = os.path.join(align_path, alignment_condition + '_' + align_dir)
                os.rename(alignment_dir, os.path.join(align_path, new_alignment_dir))

        list_file.close()
        """
        Get list of bamfiles in the format required by cuffdiff
        """
        align_dirs = os.listdir(align_path)
        for c in condition:
            rep_files = []
            for d in align_dirs:
                path, dir = os.path.split(d)
                if c in dir:
                    allbamfiles = glob.glob(os.path.join(align_path, d + '/*.bam'))
                    if len(allbamfiles) == 0:
                        raise ValueError('bam file does not exist in {}'.format(d))
                    if len(allbamfiles) == 1:
                        bfile = allbamfiles[0]
                    elif len(allbamfiles) > 1:
                        bfile = os.path.join(align_path, d + '/accepted_hits.bam')
                    if os.path.exists(bfile):
                        rep_files.append(bfile)
                    else:
                        raise ValueError('{} does not exist'.format(bfile))
            if len(rep_files) > 0:
                bam_files.append(' ' + ','.join(bf for bf in rep_files))

        output_data['assembly_file'] = assembly_file
        output_data['condition'] = condition
        output_data['bam_files'] = bam_files
        return output_data

    def _get_setapi_expressionset_data(self, expr_obj_data, result_directory):
        """
        Get data from expressionset object in the form required 
        for input to cuffmerge and cuffdiff
        """
        self.logger.info('Getting data from SETAPI expression set input')
        output_data = dict()
        condition = list()
        bam_files = list()

        assembly_file = os.path.join(result_directory, "assembly_gtf.txt")
        list_file = open(assembly_file, 'w')

        items = expr_obj_data.get('items')
        for item in items:
            """
            assembly_gtf.txt will contain the file paths of all .gtf files 
            in the expressionset. Used as input to cuffmerge.
            """
            expression_ref = item['ref']
            expression_retval = self.eu.download_expression({'source_ref': expression_ref})
            expression_dir = expression_retval.get('destination_dir')
            e_file_path = os.path.join(expression_dir, "transcripts.gtf")

            if os.path.exists(e_file_path):
                self.logger.info('Adding:  ' + expression_ref + ':, ' + e_file_path)
                list_file.write("{0}\n".format(e_file_path))
            else:
                raise ValueError(e_file_path + " not found")
            """
            Create a list of all conditions in expressionset. Used as input to cuffdiff.
            """
            expression_data = self.ws_client.get_objects2(
                {'objects':
                     [{'ref': expression_ref}]})['data'][0]['data']
            expression_condition = expression_data.get('condition')
            if expression_condition not in condition:
                condition.append(expression_condition)
            """
            Create a list of bam files in alignment set. Used as input to cuffdiff.
            """
            alignment_ref = expression_data['mapped_rnaseq_alignment'].values()[0]
            alignment_retval = self.rau.download_alignment({'source_ref': alignment_ref})
            alignment_dir = alignment_retval.get('destination_dir')
            align_path, align_dir = os.path.split(alignment_dir)
            new_alignment_dir = os.path.join(align_path, expression_condition + '_' + align_dir)
            os.rename(alignment_dir, os.path.join(align_path, new_alignment_dir))

        list_file.close()

        """
        Get gtf file from genome_ref. Used as input to cuffmerge.
        """
        output_data['genome_id'] = expression_data.get('genome_id')
        output_data['gtf_file_path'] = self._get_genome_gtf_file(output_data['genome_id'],
                                                                 self.scratch)
        """
        Get list of bamfiles in the format required by cuffdiff
        """
        align_dirs = os.listdir(align_path)
        for c in condition:
            rep_files = []
            for d in align_dirs:
                path, dir = os.path.split(d)
                if c in dir:
                    allbamfiles = glob.glob(os.path.join(align_path, d + '/*.bam'))
                    if len(allbamfiles) == 0:
                        raise ValueError('bam file does not exist in {}'.format(d))
                    if len(allbamfiles) == 1:
                        bfile = allbamfiles[0]
                    elif len(allbamfiles) > 1:
                        bfile = os.path.join(align_path, d + '/accepted_hits.bam')
                    if os.path.exists(bfile):
                        rep_files.append(bfile)
                    else:
                        raise ValueError('{} does not exist'.format(bfile))
            if len(rep_files) > 0:
                bam_files.append(' ' + ','.join(bf for bf in rep_files))

        output_data['assembly_file'] = assembly_file
        output_data['condition'] = condition
        output_data['bam_files'] = bam_files
        return output_data

    def _get_expressionset_data(self, expressionset_ref, result_directory):

        exprset_obj = self.ws_client.get_objects2(
            {'objects': [{'ref': expressionset_ref}]})['data'][0]

        expr_set_obj_type = exprset_obj.get('info')[2]
        if re.match('KBaseRNASeq.RNASeqExpressionSet-\d.\d', expr_set_obj_type):
            return self._get_rnaseq_expressionset_data(exprset_obj.get('data'), result_directory)
        elif re.match('KBaseSets.ExpressionSet-\d.\d', expr_set_obj_type):
            return self._get_setapi_expressionset_data(exprset_obj.get('data'), result_directory)
        else:
            raise TypeError(self.PARAM_IN_EXPSET_REF + ' should be of type ' +
                            'KBaseRNASeq.RNASeqExpressionSet ' +
                            'or KBaseSets.ExpressionSet')

    def _assemble_cuffdiff_command(self, params, expressionset_data, merged_gtf, output_dir):

        bam_files = " ".join(expressionset_data.get('bam_files'))
        t_labels = ",".join(expressionset_data.get('condition'))

        # output_dir = os.path.join(cuffdiff_dir, self.method_params['output_obj_name'])

        cuffdiff_command = (' -p ' + str(self.num_threads))
        """
        Set Advanced parameters for Cuffdiff
        """

        if ('time_series' in params and params['time_series'] != 0):
            cuffdiff_command += (' -T ')
        if ('min_alignment_count' in params and
                    params['min_alignment_count'] is not None):
            cuffdiff_command += (' -c ' + str(params['min_alignment_count']))
        if ('multi_read_correct' in params and
                        params['multi_read_correct'] != 0):
            cuffdiff_command += (' --multi-read-correct ')
        if ('library_type' in params and
                    params['library_type'] is not None):
            cuffdiff_command += (' --library-type ' + params['library_type'])
        if ('library_norm_method' in params and
                        params['library_norm_method'] is not None):
            cuffdiff_command += (' --library-norm-method ' + params['library_norm_method'])

        cuffdiff_command += " -o {0} -L {1} -u {2} {3}".format(output_dir,
                                                               t_labels,
                                                               merged_gtf,
                                                               bam_files)
        return cuffdiff_command

    def __init__(self, config, services, logger=None):
        self.config = config
        self.logger = logger
        self.callback_url = os.environ['SDK_CALLBACK_URL']
        self.scratch = os.path.join(config['scratch'], 'cuffdiff_merge_' + str(uuid.uuid4()))
        self.ws_url = config['workspace-url']
        self.services = services
        self.ws_client = Workspace(self.services['workspace_service_url'])
        self.dfu = DataFileUtil(self.callback_url)
        self.gfu = GenomeFileUtil(self.callback_url)
        self.rau = ReadsAlignmentUtils(self.callback_url)
        self.eu = ExpressionUtils(self.callback_url)
        self.deu = DifferentialExpressionUtils(self.callback_url)
        self.cuffmerge_runner = CuffMerge(config, logger)
        self.num_threads = mp.cpu_count()
        handler_utils._mkdir_p(self.scratch)

    def run_cuffdiff(self, params):
        """
        Check input parameters
        """
        self._process_params(params)

        expressionset_ref = params.get('expressionset_ref')
        result_directory = os.path.join(self.scratch, 'expset_' + str(uuid.uuid4()))
        handler_utils._mkdir_p(result_directory)

        """
        Get data from expressionset in a format needed for cuffmerge and cuffdiff
        """
        expressionset_data = self._get_expressionset_data(expressionset_ref, result_directory)

        """
        Run cuffmerge
        """
        cuffmerge_dir = os.path.join(self.scratch, "cuffmerge_" + str(uuid.uuid4()))
        merged_gtf = self.cuffmerge_runner.run_cuffmerge(cuffmerge_dir,
                                                         self.num_threads,
                                                         expressionset_data.get('gtf_file_path'),
                                                         expressionset_data.get('assembly_file'))
        self.logger.info('MERGED GTF FILE: ' + merged_gtf)

        """
        Assemble parameters and run cuffdiff
        """
        cuffdiff_dir = os.path.join(self.scratch, "cuffdiff_" + str(uuid.uuid4()))
        handler_utils._mkdir_p(cuffdiff_dir)

        cuffdiff_command = self._assemble_cuffdiff_command(params,
                                                           expressionset_data,
                                                           merged_gtf,
                                                           cuffdiff_dir)
        try:
            ret = script_utils.runProgram(self.logger,
                                          "cuffdiff",
                                          cuffdiff_command,
                                          None,
                                          cuffdiff_dir)
            result = ret["result"]
            for line in result.splitlines(False):
                self.logger.info(line)
                stderr = ret["stderr"]
                prev_value = ''
                for line in stderr.splitlines(False):
                    if line.startswith('> Processing Locus'):
                        words = line.split()
                        cur_value = words[len(words) - 1]
                        if prev_value != cur_value:
                            prev_value = cur_value
                            self.logger.info(line)
                        else:
                            prev_value = ''
                            self.logger.info(line)
        except Exception, e:
            raise Exception("Error executing cuffdiff {0},{1}".format(cuffdiff_command, e))

        """
        Save differential expression data with files for all condition pairs
        """
        de_data = process_cuffdiff_file(os.path.join(cuffdiff_dir, 'gene_exp.diff'),
                                        self.scratch)

        diffexpr_params = {'destination_ref': params.get(self.PARAM_IN_WS_NAME) + '/' +
                                              params.get(self.PARAM_IN_OBJ_NAME),
                           'genome_ref': expressionset_data['genome_id'],
                           'tool_used': 'cuffdiff',
                           'tool_version': os.environ['VERSION'],
                           'diffexpr_data': de_data
                           }

        dems_ref = self.deu.save_differential_expression_matrix_set(diffexpr_params).get('diffExprMatrixSet_ref')

        returnVal = {'diffExprMatrixSet_ref': dems_ref,
                     'destination_dir': cuffdiff_dir
                     }

        report_output = self._generate_report(dems_ref,
                                              expressionset_data['genome_id'],
                                              params,
                                              cuffdiff_dir)
        returnVal.update(report_output)
        return returnVal


