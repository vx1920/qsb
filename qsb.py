# ----------------------------------------------
# qsb.py, https://github.com/vx1920/qsb
# - Qt SQLite Data Browser/Viewer/Editor
# - view DB/Table information
# - execute SQL query
# - ODBC support can be added later
# ----------------------------------------------
import sys
from PyQt5        import QtGui, QtCore
from PyQt5.QtCore import (
     Qt, QModelIndex, QEvent, pyqtSlot,
     QItemSelection, QItemSelectionModel)
from PyQt5.QtSql  import (
     QSqlDatabase, QSqlTableModel,
     QSqlQuery, QSqlQueryModel)
from PyQt5.QtWidgets import (
     QAction, QMessageBox,
     QApplication, QFileDialog,
     QMainWindow, QMenu, QMenuBar,
     QVBoxLayout, QStatusBar,
     QWidget, QSplitter, QTableView,
     QAbstractItemView,
     QStyleFactory,
     QTextEdit, QListWidget, QListWidgetItem)


class CMyListWidgetItem(QListWidgetItem):
  IT_NOTYPE         =  0
  IT_TABLE_READONLY = 10  # read only table, like sqlite_master
  IT_TABLE_EDITABLE = 20  # reqular editable table
  IT_VIEW_QUERY     = 30  # read only query result

  def __init__(self) :
    super(CMyListWidgetItem, self).__init__()
    self.itmType = 0

  def __init__(self, txt, tp) :
    super(CMyListWidgetItem, self).__init__(txt)
    self.itmType = tp


# Table list for current DB in the left panel
class CMyListWidget(QListWidget):
  def __init__(self, parent) :
    super(CMyListWidget, self).__init__()
    #print("CMyListWidget:ctor")
    self.objParent = parent

    # self.resize(300,120)  # Resize width and height
    self.itemClicked.connect(self.Clicked)
    self.setFont(self.objParent.fntUse) 		
  # end __init__()


  # TODO: proper handle non-SQLITE
  def fillTableList(self) :
    self.clear()
    dbMasterTable = "sqlite_master"
    itm = CMyListWidgetItem(dbMasterTable, CMyListWidgetItem.IT_TABLE_READONLY)
    self.addItem(itm)

    #lstNamesOfTables = sorted( self.objParent.dbConn.tables() )
    #print("fillTableList:")
    #for nm in lstNamesOfTables :
    #  itm = CMyListWidgetItem(nm, CMyListWidgetItem.ITMTYPE_TABLE)
    #  self.addItem(itm);

    # tables and views from [sqlite_master]:
    tSQL = "SELECT [type], [name] FROM [%s]" % (dbMasterTable)
    tSQL += " ORDER BY [%s]" % ( "name" )
    #print(tSQL)
  
    objQuery = QSqlQuery()
    objQuery.prepare(tSQL)
    objQuery.exec_()
    rc = objQuery.first()
    while (rc) :
      # value(X) returns field X value:
      # either by "name" or by 0-based index in field list
      tp = objQuery.value(0)
      nm = objQuery.value(1)
      #print("tp: %-8s nm: %s" % (tp, nm) )

      itm = None
      if tp == "table" :
        itm = CMyListWidgetItem(nm, CMyListWidgetItem.IT_TABLE_EDITABLE)
      if tp == "view" :
        itm = CMyListWidgetItem(nm, CMyListWidgetItem.IT_VIEW_QUERY)
      if itm is not None:
        self.addItem(itm)
      rc = objQuery.next()


  # show table definition: 1 row per field
  def showTableDefinition(self) :
    if (self.objParent.tableView is None) :
      self.objParent.tableView = CMyTableView(self.objParent)
      self.objParent.splitVRight.replaceWidget(0 , self.objParent.tableView)
    self.objParent.tableView.initTableView(CMyTableView.initForTableInfo)


  def Clicked(self, item) : # LeftClick to view table data in TablePanel
    ##print("You clicked: %s tp: %s" %  (item.text() , item.itmType) )	
    self.objParent.dbTableName = item.text()
    self.objParent.dbTableType = item.itmType
    self.objParent.statusBar().showMessage('TableData: ' + self.objParent.dbTableName)

    # call member of another class and pass there ptr to that [another] class method:
    self.objParent.initTableView(CMyTableView.initForSingleTable)
    #self.objParent.initTableView(MyMainWidget.initForSingleTable) # same as above


  # right click mouse in TableList: show table with field info
  # can be used instead of contextMenuEvent()
  #def mousePressEvent(self, event) :
  #  super(CMyListWidget, self).mousePressEvent(event) # base will set currentItem()
  #  if event.button() == Qt.RightButton:
  #   self.objParent.dbTableName = self.currentItem().text()
  #   self.objParent.dbTableType = self.currentItem().itmType
  #   self.showTableDefinition()
  # end mousePressEvent()


  # RightClick normally mapped to "context menu event"
  def contextMenuEvent(self, evnt):
    #print("CMyListWidget:contextMenuEvent begin (RightClick)")
    self.objParent.dbTableName = self.currentItem().text()
    self.objParent.dbTableType = self.currentItem().itmType
    self.showTableDefinition()

# end class CMyListWidget


class CMyTextEdit(QTextEdit) :
  def __init__(self, parent) :
    super(CMyTextEdit, self).__init__()
    self.objParent = parent
    self.setFont(self.objParent.fntUse) 		
    self.setAcceptRichText(False)
  # end __init__()
# end class


class CMyTableView(QTableView) :
  def __init__(self, parent) :
    super(CMyTableView, self).__init__()
    #print("CMyTableView:ctor")
    self.objParent = parent
    self.setFont(self.objParent.fntUse) 		
    self.horizontalHeader().setFont(self.objParent.fntUse) 		
    self.clicked.connect(self.tblClicked)

    self.resetView()
  # end __init__()


  def resetView(self) :
    #print("CMyTableView: resetView")
    self.tableQuery  = None
    self.tableModel  = None
    self.curCellData = None
    self.curCellCol  = 0
    self.curCellRow  = 0

    # 0+ means autoshow this [0...N] columnn in current row in TextPane :
    self.cellColToShow = -1
    self.curCellRowOld = 0 # avoid re-copy same cell if column changed, while row is same
    self.actAutoCopy   = None # menu action to set check status on/off
    self.actCopyToText = None

    self.nRowCount  = 0
    self.fCanModify = False
  # end resetView()


  # may be uncommented to trace actual destruction moment or add there something useful
  #def __del__(self) :
  ##print("CMyTableView: Destructor called")
  ##return


  # it did work for mouse navigation, NOT for keyboard move/select 
  # if uncomment here - better to comment in onSelectionChanged
  def tblClicked(self, itm) :
    #print("CMyTableView:tblClicked, content:")  # test
    #cellContent = itm.data()
    #sf = "Cell:{}".format(cellContent)
    #self.objParent.statusBar().showMessage(sf)
    #print(sf)
    return


  # RightClick creates 'contextMenu' event
  def contextMenuEvent(self, objEvent):
    #print("contextMenuEvent begin (RightClick), ColToShow:" ,
    #      self.cellColToShow)
    menu = QMenu()
    menu.addAction( QAction(
      "Copy to Text" , self,
      statusTip = "Copy to Text Panel",
      triggered = self.doActCopyToText ))

    self.actCopyToText = QAction(
      "Copy from Text Panel", self,
      statusTip = "Copy from Text Panel",
      triggered = self.doActCopyFromText)
    menu.addAction(self.actCopyToText)
    if not self.fCanModify:
      self.actCopyToText.setDisabled(True)

    self.actAutoCopy = QAction("Auto Copy On/Off", self,
      statusTip = "Toggle AutoCopy to Text Panel",
      checkable = True,  # enable chack box for this item
      triggered = self.doActToggleAutoCopyToText)
    if self.cellColToShow == self.curCellCol : # current column AutoShow is ON
      self.actAutoCopy.setChecked(True)        # set check box On in menu item 
      #print("contextMenuEvent AutoCopy setChecked")
    menu.addAction(self.actAutoCopy)

    # draw menu in position where RightClick took place:
    menu.exec_(self.mapToGlobal(objEvent.pos())) # QAction returned
  # end contextMenuEvent()


  def doActCopyToText(self) :
    print("doActCopyToText")
    self.objParent.txtEdit.setPlainText(
         self.getCellData(self.curCellRow, self.curCellCol) )
    return


  # only for editable tables:
  def doActCopyFromText(self) :
    print("doActCopyFromText")
    self.setCellData(self.curCellRow, self.curCellCol,
                     self.objParent.txtEdit.toPlainText() )
    return


  def doActToggleAutoCopyToText(self) :
    #print("bgn doActToggleAutoCopyToText, ColToShow:" , self.cellColToShow)
    if self.cellColToShow !=  self.curCellCol: # AutoCopy at lest for current column
      self.cellColToShow = self.curCellCol # enable it on current column
      self.objParent.txtEdit.setPlainText( # also copy to text for the first time
        self.getCellData(self.curCellRow, self.curCellCol) )
    else :
      self.cellColToShow = -1   # it was On, so make it Off

    #print("end doActToggleAutoCopyToText, ColToShow:" , self.cellColToShow)
    return
  # end doActToggleAutoCopyToText()


  # safe, only if TableModel present: delete previos QTableModel 
  # QTableModel object remains as valid and another can be re-used
  # to show another data 
  def clearTableView(self) :
    if self is None:  # just in case
      return
    if (self.tableModel is not None) :
      self.setModel(None)
      del self.tableModel
      self.tableModel = None


  def dumpSelItems(self, sTitle, itms, doLast=False) :
    print(sTitle, ":" , end="", sep="")
    for ix in itms:  # QItemSelection items in the list
      print(" " , ix.data() , end="", sep="")
    print() # it will print final EOL

    if doLast: 
      lng = len(itms)
      print("   Lng:" , lng, end="")
      if lng > 0:
        print(" LastData:", itms[lng - 1].data(), end = "")
      print() # it will print final EOL
  # end dumpSelItems()


  # dumb counting, but maybe no better way
  # Commented lines below produce wrong numbers:
  # print("Query RecordCount=%d Size=%d" %
  #    (qry.record().count() , qry.size()) )
  def countQueryRows(self) :
    self.nRowCount = 0
    rc = self.tableQuery.first()
    while (rc) :
      self.nRowCount += 1
      rc = self.tableQuery.next()


  # access cell data using QTableModel, 0-based integer indexes:
  def getCellData(self, nRow, nCol) :
    qIndx = self.tableModel.index(nRow, nCol, QModelIndex())
    return str( qIndx.data(Qt.DisplayRole) )  # convert data to visible string


  def setCellData(self, nRow, nCol, val) :
    qIndx = self.tableModel.index(nRow, nCol, QModelIndex())
    self.tableModel.setData(qIndx, val)



  @pyqtSlot('QItemSelection', 'QItemSelection')
  def onSelectionChanged(self, selected, deselected):
    self.curCellRowOld = self.curCellRow
    self.curCellRow = self.selectionModel().currentIndex().row()
    self.curCellCol = self.selectionModel().currentIndex().column()
    #print("onSelectionChanged LngSel=%d LngDes=%d CurRow=%d CurCol=%d" % (
    #      len(selected.indexes()), len(deselected.indexes()),
    #      self.curCellRow, self.curCellCol  ))

    # depending upon did we selection or deselection -
    # one of these two has something, while another is empty
    #self.dumpSelItems("Sel" , selected.indexes())
    #self.dumpSelItems("Des" , deselected.indexes())

    curSel =  self.selectedIndexes() # list of currently selected items
    #self.dumpSelItems("Cur" , curSel, doLast = True)

    lng = len(curSel)
    # normally current item is selected, but no problem if not...
    if lng > 0 :
      self.curCellData = curSel[lng - 1].data()   # take data from last item
      sf = "Cell:{}".format(self.curCellData)
      self.objParent.statusBar().showMessage(sf)  # show current in statusBar

    # AutoCopy cell data Text (may be Off, may be not same as current above)
    # Only particular column here, need re-copy only when row is changed.
    if self.cellColToShow >= 0 and self.curCellRow != self.curCellRowOld:
      self.objParent.txtEdit.setPlainText(
        self.getCellData(self.curCellRow, self.cellColToShow) )

    return
  # end onSelChanged()



  # ? how to handle comma separator (argSep==',') or NewLine inside value.
  def exportTableData(self, argTitle, argSep = ",") :
    if self is None or self.tableModel is None:
      return

    sFileName, _ = QFileDialog.getSaveFileName(
         None, argTitle, ".",
         "(*.txt);; All Files (*.*)" )
    if sFileName == "" or sFileName is None:
      return

    f = open(sFileName, 'w')
    mod = self.tableModel
    for nRow in range(mod.rowCount()):
      for nCol in range(mod.columnCount()):
        if nCol > 0: # separator before each item except first one
          f.write(argSep)
        f.write( self.getCellData(nRow, nCol) )
      f.write("\n")

    f.close()
  # end exportTableData()


  def addRow(self):
    if not self.fCanModify:
      return

    #print("TableView:addRow begin")
    if self.selectionModel().hasSelection() :
      row =  self.selectionModel().selectedIndexes()[0].row()
    else:
      row =  self.nRowCount ### tableModel.rowCount()

    ret = self.tableModel.insertRow(row)
    if ret:
      self.selectRow(row)
      item = self.selectedIndexes()[0]
      self.tableModel.setData(item, str(""))

    #print("TableView:addRow done")
    return
  # end addRow()


  def delRow(self):
    if not self.fCanModify:
      return
    row = self.currentIndex().row()
    self.tableModel.removeRow(row)
    self.objParent.initTableView(CMyTableView.initForSingleTable)
    self.selectRow(row)
    return
  # end delRow()


  # single table to view, it will be editable
  # this is method for decoration by initTableView
  def initForSingleTable(self) :
    #print("initForSingleTable")
    objModel = QSqlTableModel()  # data model is single table
    objModel.setTable(self.objParent.dbTableName)
    if self.objParent.dbTableType == CMyListWidgetItem.IT_TABLE_EDITABLE :
      objModel.setEditStrategy(QSqlTableModel.OnFieldChange)
      self.setEditTriggers(QTableView.AllEditTriggers) # AbstractItemView
      self.fCanModify = True
    else: 
      self.setEditTriggers(QTableView.NoEditTriggers)
      self.fCanModify = False
 
    objModel.select()
    self.tableQuery = objModel.query()
    self.countQueryRows()
    self.objParent.setWindowTitle("%s :: %s (%d rows)" %
      (self.objParent.dbFileName, self.objParent.dbTableName, self.nRowCount) )

    return objModel
  # end initForSingleTable()


  # table as query result, it will be NOT editable (read-only)
  def executeQuery(self, sqlStatement) :
    #print("executeQuery:" , sqlStatement)
    self.nRowCount  = 0
    self.tableQuery = QSqlQuery(self.objParent.dbConn)
    rc = self.tableQuery.prepare(sqlStatement)
    if (not rc) :
      #print("PrepQueryErr: ", self.tableQuery.lastError().text() )
      self.objParent.showTextResults(
         "tableQuery.prepare error: ",
         self.tableQuery.lastError().text() )
      return

    # Info from RiverBank (Qt for Python developer):
    # in versions prior to PyQt 5.11.2, the exec() function with no arguments
    # could not execute the SQL statement with parameters set by prepare()
    # and bindValue() [exec(NoArgs) not defined], but exec_(NoArg) function
    # is OK.
    # There is a bug in versions of PyQt earlier than 5.11.2 and
    # it was fixed in PyQt5 version 5.11.2 and later: no QTableQuery.exec(void).
    # As of JUL-2021: Win64 Python 3.9.5 uses PyQt5-5.15.4, while latest Anaconda uses 5.9.2
    # Usage of exec_(NoArgs) should work in wider range of versions, 
    # including Conda qt+pyqt (which is PyQt5 5.9.2 in abobe date).
    rc = self.tableQuery.exec_()  # or: exec() # in NEW PyQt5 (after 5.11.2)
    if (not rc) :
      #print("QueryExecErr: ", self.tableQuery.lastError().text() )
      #print("dbErr: ", self.tableQuery.lastError().databaseText() )
      self.showTextResults(
           "QTableQuery.exec error:",
           self.tableQuery.lastError().text(),
           "dbErr: " + self.tableQuery.lastError().databaseText()  )
      return None

    self.objParent.listTables.fillTableList()
    self.countQueryRows()
    objTableModel = QSqlQueryModel()
    objTableModel.setQuery(self.tableQuery)
    return objTableModel
  # end executeQuery()


  # this is method for "simple decoration" by initTableView
  # (ptr to this member function to be passes there as arg)
  def initForQuery(self) :
    objTableModel = self.executeQuery( self.objParent.txtEdit.toPlainText() )
    self.objParent.setWindowTitle("%s :: QueryRun (%d rows)"
            % (self.objParent.dbFileName, self.nRowCount) )

    self.fCanModify = False
    return objTableModel
  # end initForQuery()


  # SQLITE table info only for now, something else have to be done for ODBC
  def initForTableInfo(self) :
    #print("initForTableInfo: nm=%s tp=%d" %
    #     (self.objParent.dbTableName , self.objParent.dbTableType) )
    if ((self.objParent.dbTableType == CMyListWidgetItem.IT_TABLE_READONLY) or 
        (self.objParent.dbTableType == CMyListWidgetItem.IT_TABLE_EDITABLE)) :
      sqlStmt = "PRAGMA TABLE_INFO('%s')" % (self.objParent.dbTableName)
      objTableModel = self.executeQuery( sqlStmt ) 

      self.objParent.setWindowTitle("%s :: %s :: Information (%d fields)"
          % (self.objParent.dbFileName, self.objParent.dbTableName, self.nRowCount) )
      self.objParent.statusBar().showMessage('TableFields: ' + self.objParent.dbTableName)
    elif (self.objParent.dbTableType == CMyListWidgetItem.IT_VIEW_QUERY) :
      #print("initForTableInfo: VIEW_QUERY")
      sqlStmt = "SELECT [sql] FROM [sqlite_master] WHERE [name]='%s'"
      sqlStmt = sqlStmt % (self.objParent.dbTableName)
      objTableModel = self.executeQuery( sqlStmt ) 

      self.objParent.setWindowTitle("%s :: view %s :: sql"
          % (self.objParent.dbFileName, self.objParent.dbTableName) )
      self.objParent.statusBar().showMessage('View Definition: ' + self.objParent.dbTableName)

      # now switch to text panel:
      self.tableQuery.first()
      self.objParent.showTextResults( self.tableQuery.value(0) )
    else :
      print("TblInfo: type=%d" % (self.objParent.dbTableType) )
      pass

    self.fCanModify = False
    return objTableModel # QTableModel
  # end initForTableInfo()


  # complete [re]initialization, called from main.initTableView()
  # something like MFG CView:Update called from CDoc:UpdateAllViews()
  def initTableView(self, initFor) :
    self.resetView()
    self.setModel(None)
    if (self.tableModel is not None) :
      del self.tableModel
      self.objParent.tableModel = None

    # ptr to member function passed here as an arg, proper tableModel to be created
    self.tableModel = initFor(self)
    if (self.tableModel is not None) :
      self.setModel(self.tableModel)

    # next two lines are very important, onSelectionChanged() defined later
    # it is also important to have tableModel already active to get
    # properly working QSelectionModel below (to connect callback): 
    selection_model = self.selectionModel()
    selection_model.selectionChanged.connect(self.onSelectionChanged)
  # end initTableView
# end class CMyTableView



class MyMainWidget(QMainWindow) :
  def __init__(self) :
    super(MyMainWidget, self).__init__() # init base class

    # member variables listed here:
    self.dbConn      = None
    self.dbConnType  = "QSQLITE" # other types can be used later
    self.dbFileName  = None
    self.dbTableName = None    # current table name in CMyTableView
    self.dbTableType = 0
    self.tableView   = None    # entire table (editable) or SQL query results
    self.txtResults  = None    # SQL errs, alternating with tableView in same panel
    self.listTables  = None    # widget for list of the tables in current DB
    self.txtEdit     = None    # BottomRight TextEdit widget to enter SQL query 
    self.wdgtCentral = None
    self.objApp      = None
    self.fntUse      = None
    self.layoutMain  = None
    self.splitHMain  = None
    self.splitVRight = None
  # end __init__()
	

# may be uncommented to trace actual destruction moment
  # def __del__(self) :
  #   print("MyMainWidget: Destructor called")
  #   return


# ----------------------------------------------------------------------
# Layout is splitted view with 3 panels: lstTables, tblView, txtEdit
# txtEdit used to edit SQL script, tblView shows resulting table
# or it can show errors in SQL, tblView wull be replaced with txtResults
#  ----------.-----------------
#  lstTables | tblView
#  ...       | ...
#  ...       |-----------------
#  ...       | txtEdit
#            |  ...
# ----------------------------------------------------------------------
  def initLayout(self) :  # GUI items initialization
    if self.layoutMain is not None : # ensure that it works only once
      return

    self.tableView  = CMyTableView(self)   # right panel: table view above 
    self.txtEdit    = CMyTextEdit(self)    # and TextEdit below of splitVert
    self.listTables = CMyListWidget(self)  # on the left side of main splitter

    # prepare layout (by splitters):
    self.splitHMain = QSplitter(Qt.Horizontal)  # main splitter between left and right panels
    self.splitVRight = QSplitter(Qt.Vertical)   # splitter with panels above and below
    self.splitVRight.addWidget(self.tableView)  # add panel above splitter
    self.splitVRight.addWidget(self.txtEdit)    # add panel below splitter
    # set height ratio for top/bottom panels as 6:1
    self.splitVRight.setStretchFactor(0,6)
    self.splitVRight.setStretchFactor(1,1)

    # now add panels to the left and right of main splitter:
    self.splitHMain.addWidget(self.listTables)  # left from splitter
    self.splitHMain.addWidget(self.splitVRight)      # right from splitter
    # set width ratio for left/right panels as 1:4
    self.splitHMain.setStretchFactor(0, 1)
    self.splitHMain.setStretchFactor(1, 4)

    menubar = self.createMenuBarAndActions()
    # now we have all the widgets on left and right from splitHMain
    self.wdgtCentral = QWidget()
    self.layoutMain = QVBoxLayout(self.wdgtCentral)
    # main layout, add there menubar and main splitter:
    self.layoutMain.setMenuBar(menubar)
    # never addWidget(menubar): "bar" will take  half of window height

    self.statusBar().showMessage('View tables.')
    #self.setStatusbar( QStatusBar() )

    self.layoutMain.addWidget(self.splitHMain)
    self.wdgtCentral.setLayout(self.layoutMain)
    self.setCentralWidget(self.wdgtCentral)  # finally set CentralWidget in QMainWindow

    QApplication.setStyle(QStyleFactory.create('Cleanlooks'))
    self.setGeometry(200, 200, 1400, 900) # wnd: position,size
  # end initLayout()


  #def tblClicked(self, itm) :
  #  #print("Table Cell Clicked, content:")  # test
  #  cellContent = itm.data()
  #  sf = "Cell:{}".format(cellContent)
  #  self.statusBar().showMessage(sf)
  #  #print(sf)


  def initUI(self) :  # GUI items initialization
    self.openDB()
    self.fntUse = QtGui.QFont()
    self.fntUse.setPointSize(12)

    # pass ptr to this class member method:
    self.initLayout()
    self.tableView.initTableView(CMyTableView.initForSingleTable)
    self.listTables.fillTableList()
  # end initUI()


  def initTableView(self, initFor) :
    self.resetView()

    # parent's "ptr to member function" passed here as an arg,
    # proper tableModel to be created in it, proper objPtr provided:
    self.tableModel = initFor(self.objParent)
    if (self.tableModel is not None) :
      self.setModel(self.tableModel) # apply data to viewer

    # next two lines are very important, onSelectionChanged() defined later
    # it is also important to have QTableModel (i.e. data model) already active
    # to have QSelectionModel work peoperly (to connect callback): 
    selection_model = self.selectionModel()
    selection_model.selectionChanged.connect(self.onSelectionChanged)
  # end initTableView


  def createMenuBarAndActions(self) :
    menubar = QMenuBar()
    menuDataBase = menubar.addMenu("DataBase")
    menuDataBase.addAction("New")
    menuDataBase.addAction( QAction(
      "OpenSQLITE", self, # shortcut="Ctrl+O",
      statusTip="Open DB file",
      triggered = self.doActFileOpenDB ))

    # special syntax variable assignment op, '=' means passing keyed arg instead 
    actOpenODBC = QAction(
      "OpenODBC", self, # shortcut="Ctrl+O",
      statusTip = "Open ODBC data source",
      triggered = self.doActOpenODBC)
    actOpenODBC.setDisabled(True) # enable later, when implemented
    menuDataBase.addAction(actOpenODBC)

    ###menuDataBase.addAction("Save")
    menuDataBase.addAction( QAction(
      "Query", self,  ## shortcut="Ctrl+Enter",
      statusTip = "Execute Query from Text panel",
      triggered = self.doActQueryRun ))
    menuDataBase.addSeparator()
    menuDataBase.addAction( QAction(
      "Quit", self, shortcut="Ctrl+Q",
      statusTip = "Exit the application",
      triggered = self.doActExit ))

    menuTable = menubar.addMenu("Table")
    menuTable.addAction( QAction(
      "Export Table", self, # shortcut="Ctrl+R",
      statusTip = "Export data from current table",
      triggered = self.doActTableExportCSV ))
    menuTable.addAction( QAction(
      "Add Row", self, # shortcut="Ctrl+R",
      statusTip = "Add row to current table",
      triggered = self.doActAddRow ))
    menuTable.addAction( QAction(
      "Del Row", self, # shortcut="Ctrl+R",
      statusTip = "Delete current row from table",
      triggered = self.doActDelRow ))

    menuHelp = menubar.addMenu("Help")
    menuHelp.addAction(  QAction(
      "About", self, # shortcut="Ctrl+",
      statusTip = "Show Info",
      triggered = self.doActHelpAbout ))
    menuHelp.addAction(  QAction(
      "About PyQt", self, # shortcut="Ctrl+",
      statusTip = "Show Info PyQt",
      triggered = self.doActHelpAboutPyQt ))
    menuHelp.addAction(  QAction(
      "About Qt", self, # shortcut="Ctrl+",
      statusTip = "Show Qt Info",
      triggered = QApplication.instance().aboutQt ))

    return menubar
  # end createMenuBarAndActions()


  def closeDB(self) :
    # only particular DB connection will be properly closed/removed,
    # while all other connections (if present) remains intact
    # safe to call when DB was never opened or after some partial open after errs

    #print("closeDB begin")
    # ensure self has no more references to tableModel from tableView
    self.tableQuery = None
    if (self.tableView is not None) :
      self.tableView.clearTableView()

    if (self.dbConn is not None) :
      connName = QSqlDatabase.connectionName(self.dbConn)
      #print("closeDB connName =" , connName)
      self.dbConn.close()
      del self.dbConn
      self.dbConn = None

      # QTableModel with actove data connection was referred in CMyTableView and
      # also Query was referred to DB connection, see safe cleanup code above.
      # It was done to avoid warning ""
      # only after all references to connection are gone
      # we can remove especially that one
      QSqlDatabase.removeDatabase( connName );
      #print("closeDB done")
  # end closeDB()


  def openDB(self) :
    #print("openDB begin, file:" , self.dbFileName)
    self.closeDB() # OK to call DB if never open or after errs
    # dbConnType = "QSQLITE" means SQLite3 and above
    # ConnectionString is just path\filename.ext
    self.dbConn = QSqlDatabase.addDatabase(self.dbConnType)
    self.dbConn.setDatabaseName(self.dbFileName)  # set ConnectionString

    # Note: for dbConnType "QODBC" we have connection string as of:
    #  f'DRIVER={{SQL Server}};'\
    #  f'SERVER={SERVER_NAME};'\
    #  f'DATABASE={DATABASE_NAME}'
  # end openDB()


  # "decorator" method (callback). It "decorates" some other initForXXX
  # member methods from this class passed here  as initFor argument
  # Proper 'model' is prepared in initfor and passed to tableView
  # QTableiew widget is alternating with QTextEdit (as errors) in the same panel
  def initTableView(self, initFor) :
    #print("main:initTableView: File=<%s> Table=<%s>" %
    #      (self.dbFileName ,  self.dbTableName) )
    self.nRowCount    = 0
    if (self.tableView is None) :
      self.tableView = CMyTableView(self)
      self.splitVRight.replaceWidget(0 , self.tableView)

    if (self.txtResults is not None) :
      del self.txtResults
      self.txtResults = None

    self.tableView.initTableView(initFor)
  # end initTableView()


  # QTableView widget alternating with QTextEdit in the same panel
  # (first shows table, second shows errors in SQL instead of table)
  def showTextResults(self, txtInfo, *moreArgs) :
    if (self.txtResults is None) :
      self.txtResults = CMyTextEdit(self)

    self.splitVRight.replaceWidget(0 , self.txtResults)
    if (self.tableView is not None) :
      del self.tableView
      self.tableView = None

    self.txtResults.setText(txtInfo)
    for itm in moreArgs :
      if itm is not None :
        self.txtResults.append(itm)

    self.setWindowTitle("%s :: Query Results" % (self.dbFileName) )
  # end showTextResults()


  # menu actions implementation:
  def doActFileOpenDB(self):
    self.dbFileName, _ = QFileDialog.getOpenFileName(
      None, "Open Database File", ".",
      "DB (*.sqlite *.db *.sql3);; All Files (*.*)")

    self.dbTableName = "sqlite_master"
    self.openDB()
    self.initUI()
  # end doActFileOpenDB()


  def doActOpenODBC(self) :
    QMessageBox.warning(self, "Warning",
      "It is not emplemented yet." )


  def doActQueryRun(self) :
    self.initTableView(CMyTableView.initForQuery)


  def doActAddRow(self) :
    self.tableView.addRow()


  def doActDelRow(self) :
    self.tableView.delRow()


  # export as CommaseparatedValues 
  def doActTableExportCSV(self) :
    self.tableView.exportTableData("Export table data as CSV" , ",")


  def doActHelpAbout(self) :
    QMessageBox.about(self, "Information",
      "This is simple SQL viewer/browser based on PyQt.")


  def doActHelpAboutPyQt(self) :
    QMessageBox.about(self, "PyQt Information",
      "PyQt version %s. Python Version:\n%s" %
         (QtCore.PYQT_VERSION_STR , sys.version) )


  def doActExit(self) :
    self.closeDB()   # disconnect from DB, safely and only if connected
    self.close()     # close window 
# end class MyMainWidget


def runMain(dbFile , dbTable):
  app = QApplication(sys.argv)
  ex  = MyMainWidget()
  ex.objApp = app
  ex.dbFileName  = dbFile
  ex.dbTableName = dbTable
  ex.initUI()
  ex.show()
  rc = app.exec_()
  return rc	


def launch() :
  # default DB and Table names:
  dbFile  = 'NorthWind.db'
  dbTable = 'sqlite_master'  # SQLITE only

  # above defaults can be overridden from command line if specified:
  nArgCnt = len(sys.argv)
  if nArgCnt >= 2 :
    dbFile = sys.argv[1]
  if nArgCnt >= 3 :
    dbTable = sys.argv[2]

  rc = runMain(dbFile, dbTable)
  return rc


if __name__ == '__main__':
  launch()

# eof