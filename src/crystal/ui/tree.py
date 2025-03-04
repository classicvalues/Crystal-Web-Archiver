"""
Facade for working with wx.TreeCtrl.

This abstraction provides:
* tree nodes that can be manipulated before being added to a tree
* delegate-style event handling on tree nodes
* access to the underlying "peer" objects (i.e. wx.TreeCtrl, tree item index)
"""

from crystal.progress import OpenProjectProgressListener
from typing import Optional
import wx

_DEFAULT_TREE_ICON_SIZE = (16,16)

_DEFAULT_FOLDER_ICON_SET_CACHED = None
def _DEFAULT_FOLDER_ICON_SET():
    global _DEFAULT_FOLDER_ICON_SET_CACHED  # necessary to write to a module global
    if not _DEFAULT_FOLDER_ICON_SET_CACHED:
        _DEFAULT_FOLDER_ICON_SET_CACHED = (
            (wx.TreeItemIcon_Normal,   wx.ArtProvider.GetBitmap(wx.ART_FOLDER,      wx.ART_OTHER, _DEFAULT_TREE_ICON_SIZE)),
            (wx.TreeItemIcon_Expanded, wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN,   wx.ART_OTHER, _DEFAULT_TREE_ICON_SIZE)),
        )
    return _DEFAULT_FOLDER_ICON_SET_CACHED

_DEFAULT_FILE_ICON_SET_CACHED = None
def _DEFAULT_FILE_ICON_SET():
    global _DEFAULT_FILE_ICON_SET_CACHED    # necessary to write to a module global
    if not _DEFAULT_FILE_ICON_SET_CACHED:
        _DEFAULT_FILE_ICON_SET_CACHED = (
            (wx.TreeItemIcon_Normal,   wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, _DEFAULT_TREE_ICON_SIZE)),
        )
    return _DEFAULT_FILE_ICON_SET_CACHED

# Maps wx.EVT_TREE_ITEM_* events to names of methods on `NodeView.delegate`
# that will be called (if they exist) upon the reception of such an event.
_EVENT_TYPE_2_DELEGATE_CALLABLE_ATTR = {
    wx.EVT_TREE_ITEM_EXPANDED: 'on_expanded',
    wx.EVT_TREE_ITEM_RIGHT_CLICK: 'on_right_click',
    # TODO: Consider adding support for additional wx.EVT_TREE_ITEM_* event types
}
_EVENT_TYPE_ID_2_DELEGATE_CALLABLE_ATTR = dict(zip(
    [et.typeId for et in _EVENT_TYPE_2_DELEGATE_CALLABLE_ATTR],
    _EVENT_TYPE_2_DELEGATE_CALLABLE_ATTR.values()
))

class TreeView(object):
    """
    Displays a tree of nodes.
    
    Acts as a facade for manipulating an underlying wx.TreeCtrl.
    For advanced customization, this wx.TreeCtrl may be accessed through the `peer` attribute.
    
    Automatically creates a root NodeView (accessible via the `root` attribute),
    which will not be displayed 
    """
    
    def __init__(self, parent_peer):
        self.delegate = None
        self.peer = _OrderedTreeCtrl(parent_peer, style=wx.TR_DEFAULT_STYLE|wx.TR_HIDE_ROOT)
        
        # Setup node image registration
        self.bitmap_2_image_id = dict()
        tree_icon_size = _DEFAULT_TREE_ICON_SIZE
        self.tree_imagelist = wx.ImageList(tree_icon_size[0], tree_icon_size[1])
        self.peer.AssignImageList(self.tree_imagelist)
        
        # Create root node's view
        self._root_peer = NodeViewPeer(self, self.peer.AddRoot(''))
        self.root = NodeView()
        
        # Listen for events on peer
        for event_type in _EVENT_TYPE_2_DELEGATE_CALLABLE_ATTR:
            self.peer.Bind(event_type, self._dispatch_event, self.peer)
    
    def _get_root(self):
        return self._root
    def _set_root(self, value):
        self._root = value
        self._root._attach(self._root_peer)
    root = property(_get_root, _set_root)
    
    @property
    def selected_node(self):
        selected_node_id = self.peer.GetSelection()
        return self.peer.GetItemData(selected_node_id) if selected_node_id.IsOk() else None
    
    def get_image_id_for_bitmap(self, bitmap):
        """
        Given a wx.Bitmap, returns an image ID suitable to use as an node icon.
        Calling this multiple times with the same wx.Bitmap will return the same image ID.
        """
        if bitmap in self.bitmap_2_image_id:
            image_id = self.bitmap_2_image_id[bitmap]
        else:
            image_id = self.tree_imagelist.Add(bitmap)
            self.bitmap_2_image_id[bitmap] = image_id
        return image_id
    
    def expand(self, node_view):
        self.peer.Expand(node_view.peer.node_id)
    
    # Notified when any interesting event occurs on the peer
    def _dispatch_event(self, event):
        node_id = event.GetItem()
        node_view = self.peer.GetItemData(node_id)
        
        # Dispatch event to the node
        node_view._dispatch_event(event)
        
        # Dispatch event to my delegate
        if self.delegate:
            event_type_id = event.GetEventType()
            delegate_callable_attr = _EVENT_TYPE_ID_2_DELEGATE_CALLABLE_ATTR.get(event_type_id, None)
            if delegate_callable_attr and hasattr(self.delegate, delegate_callable_attr):
                getattr(self.delegate, delegate_callable_attr)(event, node_view)

class _OrderedTreeCtrl(wx.TreeCtrl):
    def OnCompareItems(self, item1, item2):
        item1_view = self.GetItemData(item1)
        item2_view = self.GetItemData(item2)
        return item1_view._order_index - item2_view._order_index

class NodeView(object):
    """
    Node that is (or will be) in a TreeView.
    
    Acts as a facade for manipulating a wxTreeItemId in a wxTreeCtrl. Allows modifications even
    if the underlying wxTreeItemId doesn't yet exist. For advanced customization, the wxTreeItemId
    and wxTreeCtrl may be accessed through the `peer` attribute (which is a `NodeViewPeer`)).
    
    To receive events that occur on a NodeView, assign an object to the `delegate` attribute.
    * For each event of interest, this object should implement methods of the signature:
          def on_eventname(self, event)
    * The `event` object passed to this method is a wx.Event object that can be inspected for more
      information about the event.
    * The full list of supported event names is given by
      `_EVENT_TYPE_ID_2_DELEGATE_CALLABLE_ATTR.values()`.
    """
    
    def __init__(self):
        self.delegate = None
        self.peer = None
        self._title = ''
        self._expandable = False
        self._icon_set = None
        self._children = []
    
    def _get_title(self):
        return self._title
    def _set_title(self, value):
        self._title = value
        if self.peer:
            self.peer.SetItemText(value)
    title = property(_get_title, _set_title)
    
    def _get_expandable(self):
        return self._expandable
    def _set_expandable(self, value):
        self._expandable = value
        if self.peer:
            self.peer.SetItemHasChildren(value)
            # If using default icon set, force it to update since it depends on the expandable state
            if self.icon_set is None:
                self.icon_set = self.icon_set
    expandable = property(_get_expandable, _set_expandable)
    
    def _get_icon_set(self):
        """
        A sequence of (wx.TreeItemIcon, wx.Bitmap) tuples, specifying the set of icons applicable
        to this node in various states. If None, then a default icon set is used, depending on
        whether this node is expandable.
        """
        return self._icon_set
    def _set_icon_set(self, value):
        self._icon_set = value
        if self.peer:
            effective_value = value if value is not None else (
                    _DEFAULT_FOLDER_ICON_SET() if self.expandable else _DEFAULT_FILE_ICON_SET())
            for (which, bitmap) in effective_value:
                self.peer.SetItemImage(self._tree.get_image_id_for_bitmap(bitmap), which)
    icon_set = property(_get_icon_set, _set_icon_set)
    
    def _get_children(self):
        return self._children
    def _set_children(self, new_children) -> None:
        self.set_children(new_children)
    children = property(_get_children, _set_children)
    
    def set_children(self,
            new_children,
            progress_listener: Optional[OpenProjectProgressListener]=None) -> None:
        if progress_listener is not None:
            part_count = sum([len(c.children) for c in new_children])
            progress_listener.creating_entity_tree_nodes(part_count)
        
        old_children = self._children
        self._children = new_children
        if self.peer:
            if not self.peer.GetFirstChild()[0].IsOk():
                # Add initial children
                part_index = 0
                for (index, child) in enumerate(new_children):
                    if progress_listener is not None:
                        progress_listener.creating_entity_tree_node(part_index)
                        part_index += len(child.children)
                    child._attach(NodeViewPeer(self.peer._tree, self.peer.AppendItem('')))
            else:
                # Replace existing children, preserving old ones that match new ones
                old_children_set = set(old_children)
                
                children_to_delete = old_children_set - set(new_children)
                for child in children_to_delete:
                    child.peer.Delete()
                
                children_to_add = [new_child for new_child in new_children if new_child not in old_children_set]
                for child in children_to_add:
                    child._attach(NodeViewPeer(self.peer._tree, self.peer.AppendItem('')))
                
                # Reorder children
                i = 0
                for child in new_children:
                    child._order_index = i
                    i += 1
                self.peer.SortChildren()
    
    def append_child(self, child):
        self.children = self.children + [child]
    
    @property
    def _tree(self):
        if not self.peer:
            raise ValueError('Not attached to a tree.')
        return self.peer._tree
    
    def _attach(self, peer):
        if self.peer:
            raise ValueError('Already attached to a different peer.')
        self.peer = peer
        
        # Enable navigation from peer back to this view
        peer.SetItemData(self)
        
        # Trigger property logic to update peer
        self.title = self.title
        self.expandable = self.expandable
        self.icon_set = self.icon_set
        self.children = self.children
    
    # Called when a wx.EVT_TREE_ITEM_* event occurs on this node
    def _dispatch_event(self, event):
        # Dispatch event to my delegate
        if self.delegate:
            event_type_id = event.GetEventType()
            delegate_callable_attr = _EVENT_TYPE_ID_2_DELEGATE_CALLABLE_ATTR.get(event_type_id, None)
            if delegate_callable_attr and hasattr(self.delegate, delegate_callable_attr):
                getattr(self.delegate, delegate_callable_attr)(event)

class NodeViewPeer(tuple):
    def __new__(cls, tree, node_id):
        return tuple.__new__(cls, (tree, node_id))
    
    # TODO: Only the 'tree_peer' should be stored.
    #       Remove use of this property and update constructor.
    @property
    def _tree(self):
        return self[0]
    
    @property
    def tree_peer(self):
        return self._tree.peer
    
    @property
    def node_id(self):
        return self[1]
    
    def SetItemData(self, obj):
        self.tree_peer.SetItemData(self.node_id, obj)
    
    def SetItemText(self, text):
        self.tree_peer.SetItemText(self.node_id, text)
    
    def SetItemHasChildren(self, has):
        self.tree_peer.SetItemHasChildren(self.node_id, has)
    
    def GetFirstChild(self):
        return self.tree_peer.GetFirstChild(self.node_id)
    
    def AppendItem(self, text, *args):
        return self.tree_peer.AppendItem(self.node_id, text, *args)
    
    def SetItemImage(self, image, which):
        self.tree_peer.SetItemImage(self.node_id, image, which)
    
    def Delete(self):
        self.tree_peer.Delete(self.node_id)
    
    def SortChildren(self):
        self.tree_peer.SortChildren(self.node_id)
