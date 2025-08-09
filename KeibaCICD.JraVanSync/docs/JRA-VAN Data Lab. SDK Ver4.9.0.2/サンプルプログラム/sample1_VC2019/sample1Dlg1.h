
//{{AFX_INCLUDES()
#include "jvlink.h"
//}}AFX_INCLUDES

#if !defined(AFX_SAMPLE1DLG1_H__CDA3D126_7B34_11D7_916F_0003479BEB3F__INCLUDED_)
#define AFX_SAMPLE1DLG1_H__CDA3D126_7B34_11D7_916F_0003479BEB3F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif // _MSC_VER > 1000

//========================================================================
//	JRA-VAN Data Lab. �T���v���v���O�����P(Sample1Dlg1.h)
//
//
//	 �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//	 (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================

class CSample1Dlg1 : public CDialog
{
// �\�z
public:
	CSample1Dlg1(CWnd* pParent = NULL);	// �W���̃R���X�g���N�^
	void PrintOut(CString message);
	void PrintFileList(CString message);

// �_�C�A���O �f�[�^
	//{{AFX_DATA(CSample1Dlg1)
	enum { IDD = IDD_SAMPLE1_DIALOG1 };
	CRichEditCtrl	m_strOut;
	CRichEditCtrl	m_strFileList;
	CJVLink	m_jvlink1;
	//}}AFX_DATA

	// ClassWizard �͉��z�֐��̃I�[�o�[���C�h�𐶐����܂��B
	//{{AFX_VIRTUAL(CSample1Dlg1)
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);	// DDX/DDV �̃T�|�[�g
	//}}AFX_VIRTUAL
// �C���v�������e�[�V����
protected:
	HICON m_hIcon;

	// �������ꂽ���b�Z�[�W �}�b�v�֐�
	//{{AFX_MSG(CSample1Dlg1)
	virtual BOOL OnInitDialog();
	afx_msg void OnSysCommand(UINT nID, LPARAM lParam);
	afx_msg void OnPaint();
	afx_msg HCURSOR OnQueryDragIcon();
	afx_msg void OnButton1();
	afx_msg int OnCreate(LPCREATESTRUCT lpCreateStruct);
	afx_msg void OnButton2();
	afx_msg void OnButton4();
	afx_msg void OnButton3();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
private:
	//�t�H���g
	CFont m_font;
};

//{{AFX_INSERT_LOCATION}}
// Microsoft Visual C++ �͑O�s�̒��O�ɒǉ��̐錾��}�����܂��B

#endif // !defined(AFX_SAMPLE1DLG1_H__CDA3D126_7B34_11D7_916F_0003479BEB3F__INCLUDED_)
