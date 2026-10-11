from unittest import mock
import roadmap_issue_tool as gh
import connectors
import executor


def test_owner_read_does_not_expand_write_scope():
    with mock.patch.dict('os.environ', {'BIMA_GITHUB_READ_OWNERS':'Noor-arief','BIMA_GITHUB_ALLOWED_REPOS':'Noor-arief/Bima.Ginga.ai'}, clear=True):
        assert gh._read_allowed('Noor-arief/another-private-project')
        assert not gh._allowed('Noor-arief/another-private-project')
        assert not executor._allowed('Noor-arief/another-private-project')
        assert not gh._read_allowed('someone-else/private')
        assert not gh._read_allowed('Noor-arief/../other')


def test_repository_inventory_paginates_and_filters():
    first=[{'full_name':'Noor-arief/repo'+str(i),'private':True} for i in range(100)]
    last=[{'full_name':'Noor-arief/final'}, {'full_name':'other/repo'}]
    with mock.patch.dict('os.environ', {'BIMA_GITHUB_READ_OWNERS':'Noor-arief'}, clear=True), mock.patch.object(gh,'_github',side_effect=[first,last]) as api:
        result=gh.github_list_repositories()
        assert result['total']==101 and result['complete']
        assert 'page=2' in api.call_args[0][1]


def test_connection_validates_repository_inventory():
    with mock.patch.dict('os.environ',{'BIMA_GITHUB_TOKEN':'test','BIMA_GITHUB_READ_OWNERS':'Noor-arief'},clear=True), mock.patch.object(gh,'github_list_repositories',return_value={'repositories':[{'full_name':'Noor-arief/BIMA'}],'total':1,'complete':True}):
        result=connectors.test_connector('github')
        assert result['ok'] and result['total']==1
        assert result['detail'].startswith('Connected')


def test_worker_reads_other_owner_repo():
    with mock.patch.dict('os.environ',{'BIMA_GITHUB_READ_OWNERS':'Noor-arief'},clear=True), mock.patch.object(executor,'_github',side_effect=[{'default_branch':'master'},[]]):
        assert executor.github_list_files('Noor-arief/new-project')['ref']=='master'
