//========================================================================
//  JRA-VAN Data Lab. �T���v���v���O�����P(JVLinkSample1)
//
//
//   �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//   (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================
program JVLinkSample1;

uses
  Forms,
  Unit1 in 'Unit1.pas' {frmMain},
  Unit2 in 'Unit2.pas' {frmJVLinkDialog};

{$R *.res}

begin
  Application.Initialize;
  Application.CreateForm(TfrmMain, frmMain);
  Application.CreateForm(TfrmJVLinkDialog, frmJVLinkDialog);
  Application.Run;
end.
