#if !defined(AFX_SAMPLE1DLG2_H__EB168520_7CB7_11D7_916F_0003479BEB3F__INCLUDED_)
#define AFX_SAMPLE1DLG2_H__EB168520_7CB7_11D7_916F_0003479BEB3F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif // _MSC_VER > 1000
//========================================================================
//	JRA-VAN Data Lab. �T���v���v���O�����P(sample1Dlg2.h)
//
//
//	 �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//	 (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================

/////////////////////////////////////////////////////////////////////////////
// CSample1Dlg2 �_�C�A���O

class CSample1Dlg2 : public CDialog
{
// �R���X�g���N�V����
public:
	CSample1Dlg2(CWnd* pParent = NULL);   // �W���̃R���X�g���N�^

// �_�C�A���O �f�[�^
	//{{AFX_DATA(CSample1Dlg2)
	enum { IDD = IDD_SAMPLE1_DIALOG2 };

	//}}AFX_DATA


// �I�[�o�[���C�h
	// ClassWizard �͉��z�֐��̃I�[�o�[���C�h�𐶐����܂��B
	//{{AFX_VIRTUAL(CSample1Dlg2)
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV �T�|�[�g
	//}}AFX_VIRTUAL
private:	


// �C���v�������e�[�V����
protected:
	//�I������
	void JVClosing();
	//�Ǎ��ݏ���
	void JVReading();
	// �v���O���X�o�[
	CProgressCtrl m_pgrProgress1;
	CProgressCtrl m_pgrProgress2;
	CEdit	m_txtFromDate;
	CEdit	m_txtDataSpec;
	int		m_iRadio;

	//�o�b�N�O���E���h����
	void CSample1Dlg2::PumpMessages();

	// �������ꂽ���b�Z�[�W �}�b�v�֐�
	//{{AFX_MSG(CSample1Dlg2)
	afx_msg void OnButton1();
	afx_msg void OnButton2();
	afx_msg void OnTimer(UINT nIDEvent);
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

//{{AFX_INSERT_LOCATION}}
// Microsoft Visual C++ �͑O�s�̒��O�ɒǉ��̐錾��}�����܂��B

#endif // !defined(AFX_SAMPLE1DLG2_H__EB168520_7CB7_11D7_916F_0003479BEB3F__INCLUDED_)
