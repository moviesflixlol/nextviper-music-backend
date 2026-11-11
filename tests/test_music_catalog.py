"""Use captured renderer shapes and isolated data; never call YouTube or live accounts."""
import json, os, subprocess, tempfile, unittest
from pathlib import Path
import test_auth_security as auth_tests
ROOT, BINARY = auth_tests.ROOT, auth_tests.BINARY

class CatalogParsing(unittest.TestCase):
 def test_current_search_radio_and_release_renderers(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'check.nv'
   p.write_text('import std.fs\nimport std.json\nimport "'+str(ROOT/'src/innertube')+'"\n'+''.join('print(json.stringify(innertube.parse_response(json.parse(fs.read_file('+json.dumps(str(ROOT/'tests/fixtures'/f'{name}.json'))+')))))\n' for name in ['search','radio','browse']))
   run=subprocess.run([BINARY,'run',str(p)],capture_output=True,text=True,check=True)
   search,radio,releases=map(json.loads,run.stdout.splitlines())
   self.assertTrue(any(a['name']=='Billie Eilish' and a['id'].startswith('UC') for a in search['artists']))
   self.assertTrue(search['songs']);self.assertTrue(all(t['artist']!='3:50' for t in search['songs']))
   self.assertEqual(len(radio['songs']),8);self.assertTrue(all(t['duration'] for t in radio['songs']))
   self.assertEqual(len({t['id'] for t in radio['songs']}),8)
   self.assertTrue(releases['albums']);self.assertTrue(releases['songs'])

class MusicRecommendations(auth_tests.AuthSecurity):
 @classmethod
 def prepare_sources(cls):
  p=cls.work/'src/innertube.nv';s=p.read_text();a=s.index('fn request_items(');b=s.index('fn search_all(',a)
  s=s[:a]+'''fn request_items(endpoint, extra, country):
    if endpoint == "search":
        return parse_response(json.parse(fs.read_file("search.json")))
    if endpoint == "next":
        return parse_response(json.parse(fs.read_file("radio.json")))
    return parse_response(json.parse(fs.read_file("browse.json")))

'''+s[b:];p.write_text('import std.fs\n'+s)
  for name in ['search','radio','browse']:(cls.work/f'{name}.json').write_bytes((ROOT/'tests/fixtures'/f'{name}.json').read_bytes())
 def test_10_listens_are_qualified_deduplicated_ranked_and_private(self):
  token=self.token({'userId':'usr_owner','exp':int(__import__('time').time())+600})
  base={'trackId':'V9PVRfjEBTI','title':'Birds of a Feather','artist':'Billie Eilish','thumbnail':'https://example.test/a.jpg','eventType':'listen','playedSeconds':29,'playbackId':'first'}
  self.assertEqual(self.request('/api/recommendations/event','POST',base,token=token)[0],200)
  self.assertEqual(self.request('/api/recommendations/feed',token=token)[1]['mostListened'],[])
  base['playedSeconds']=30
  for _ in range(2):self.assertEqual(self.request('/api/recommendations/event','POST',base,token=token)[0],200)
  feed=self.request('/api/recommendations/feed',token=token)[1]
  self.assertEqual(feed['mostListened'][0]['playCount'],1)
  base['playbackId']='second';self.request('/api/recommendations/event','POST',base,token=token)
  self.assertEqual(self.request('/api/recommendations/feed',token=token)[1]['mostListened'][0]['playCount'],2)
  for headers in [{},{'X-Session-Id':'usr_owner'},{'X-Device-Id':'usr_owner'}]:
   self.assertEqual(self.request('/api/recommendations/feed',headers=headers)[1]['mostListened'],[])
 def test_11_no_duplicate_sections_or_pagination(self):
  feed=self.request('/api/recommendations/feed')[1]
  ids=[t['id'] for section in ['recommendedForYou','trending','newReleases'] for t in feed[section]]
  self.assertEqual(len(ids),len(set(ids)))
  more=self.request('/api/recommendations/feed?exclude='+','.join(ids))[1]
  self.assertFalse(set(ids)&{t['id'] for t in more['recommendedForYou']})
  self.assertTrue(feed['releaseAlbums'])
 def test_12_artist_search_and_browse_validation(self):
  status, data=self.request('/api/search?q=Billie')
  self.assertEqual(status,200);self.assertTrue(data['artists']);self.assertTrue(data['results'])
  self.assertEqual(self.request('/api/browse?id=http://internal')[0],400)
  self.assertEqual(self.request('/api/related?id=no')[0],400)
  self.assertEqual(self.request('/api/related?id=V9PVRfjEBTI')[1]['results'][0]['id'],'V9PVRfjEBTI')

if __name__=='__main__':unittest.main()
