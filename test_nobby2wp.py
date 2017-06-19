import pytest

# Skip all tests here if 'wordpress_xmlrpc' module is not installed.
try:
    import nobby2wp
    noWordpress = False

    @pytest.mark.skipif(True, reason="Requires wordpress_xmlrpc")
    class FakePostIDData(nobby2wp.PostIDData):
        """
        Test class. It does not read from a file.
        """
        def __init__(self, fdata):
            self.fdata = fdata
            self.entries = self.parsePostID()
except ImportError:
    noWordpress = True


@pytest.mark.skipif(noWordpress, reason="Requires wordpress_xmlrpc")
class TestWordpressNobby():
    def test_loadPostID_simple(self):
        host = 'test@home'

        fdata = 'test@home, page, 1'
        obj = FakePostIDData(fdata)
        pid = obj.loadPostID(host, 'page')
        assert pid == [(host, 'page', '1')]

        fdata = 'test@home, post, 1'
        obj = FakePostIDData(fdata)
        pid = obj.loadPostID(host, 'post')
        assert pid == [(host, 'post', '1')]

        fdata = ''
        obj = FakePostIDData(fdata)
        pid = obj.loadPostID(host, 'post')
        assert pid == []

        fdata = 'test@home, post, 1'
        obj = FakePostIDData(fdata)
        pid = obj.loadPostID(host, 'page')
        assert pid == []

        fdata = 'test2@home, page, 1'
        obj = FakePostIDData(fdata)
        pid = obj.loadPostID(host, 'post')
        assert pid == []

    def test_loadPostID_multi(self):
        host = 'test@home'

        fdata = ('test@home, post, 1\n'
                 'test@home, page, 2\n'
                 'test@home, foo, 3')
        obj = FakePostIDData(fdata)
        p = obj.loadPostID(host, None)
        assert p == [
            (host, 'post', '1'), (host, 'page', '2'), (host, 'foo', '3')]

    def test_loadsavePostID_simple(self):
        host = 'test@home'

        # Add a new entry to an empty list.
        fdata = ''
        obj = FakePostIDData(fdata)
        obj.savePostID(host, 'page', '1')
        pid = obj.loadPostID(host, 'page')
        assert pid == [(host, 'page', '1')]

        # Add a new entry to a non-empty list.
        fdata = 'test@home, post, 1'
        obj = FakePostIDData(fdata)
        obj.savePostID(host, 'post', '1')
        pid = obj.loadPostID(host, 'post')
        assert pid == [(host, 'post', '1')]

        # savePostID must not do anything if en entry with the same type, host,
        # and already exists.
        fdata = 'test@home, page, 1'
        obj = FakePostIDData(fdata)
        pid = obj.loadPostID(host, 'page')
        assert pid == [(host, 'page', '1')]

    def test_loadsavePostID_multi(self):
        host = 'test@home'

        # Add a new entry (same as in loadsavePostID_simple, but with multiple
        # lines this time).
        fdata = ('test@home, post, 1\n'
                 'test@home, foo, 3')
        obj = FakePostIDData(fdata)
        out = obj.savePostID(host, 'page', '4')
        assert out == ('test@home, post, 1\n'
                       'test@home, foo, 3\n'
                       'test@home, page, 4\n')

        # Load `page` entry for `host`.
        pid = obj.loadPostID(host, 'page')
        assert pid == [(host, 'page', '4')]

    def test_loadsavePostID_error(self):
        host = 'test@home'

        # Must raise an error because the ID contains copies of same line. This
        # is not technically a problem, but should not happen anyway.
        fdata = ('test@home, post, 1\n'
                 'test@home, post, 1\n')
        with pytest.raises(ValueError):
            obj = FakePostIDData(fdata)
            obj.loadPostID(host, 'post')

        # Must raise an error because the ID file contains different IDs for
        # more than one entry with same type and host.
        fdata = ('test@home, post, 1\n'
                 'test@home, post, 2\n')
        with pytest.raises(ValueError):
            obj = FakePostIDData(fdata)
            obj.loadPostID(host, 'post')

        # Adding an entry that already exists must fail if the ID does not
        # match.
        fdata = 'test@home, post, 1'
        with pytest.raises(ValueError):
            obj = FakePostIDData(fdata)
            obj.savePostID(host, 'post', '2')
